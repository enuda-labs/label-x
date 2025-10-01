import decimal
import uuid
from celery import shared_task
from account.choices import BankPlatformChoices, MonthlyEarningsReleaseStatusChoices
from account.models import MonthlyReviewerEarnings, UserBankAccount
from payment.choices import TransactionTypeChoices, WithdrawalRequestInitiatedByChoices
from payment.utils import convert_usd_to_ngn
from payment.models import Transaction, WithdrawalRequest
from paystackapi.paystack import Paystack, TransferRecipient
from django.conf import settings
import logging
from django.db.models import Q


logger = logging.getLogger(__name__)

paystack = Paystack(secret_key=settings.PAYSTACK_SECRET_KEY)


@shared_task
def test_task():
    print("Test task executed successfully")
    logger.info(f'Test task executed successfully')


def initiate_monthly_usd_paystack_transfer(monthly_earning):
    labeler = monthly_earning.reviewer
    usd_amount = monthly_earning.usd_balance
    
    try:
        logger.info(f'Initiating monthly USD paystack transfer for {labeler.username} with amount {usd_amount}')
        
        ngn_amount = convert_usd_to_ngn(usd_amount)
        logger.info(f'Converted USD to NGN for {labeler.username} with amount {usd_amount} is {ngn_amount}')
        
        transaction = Transaction.objects.create(
            user=labeler,
            usd_amount = usd_amount,
            ngn_amount = ngn_amount,
            transaction_type = TransactionTypeChoices.MONTHLY_PAYMENT,
            description = "Monthly payment",
        )
        
        #get users primary bank account
        try:
            bank_account = UserBankAccount.objects.get(user=labeler, is_primary=True)
        except UserBankAccount.DoesNotExist:
            logger.error(f'No bank account found for {labeler.username}, skipping payment processing')
            transaction.mark_failed(reason="No bank account found for this user")
            #TODO: SEND EMAIL TO THE LABELLER TELLING THEM TO ADD A BANK ACCOUNT
            return False
        
        reference = str(uuid.uuid4())
    
        withdrawal_request= WithdrawalRequest.objects.create(
            account_number=bank_account.account_number,
            bank_code=bank_account.bank_code,
            bank_name=bank_account.bank_name,
            reference=reference,
            transaction=transaction,
            initiated_by=WithdrawalRequestInitiatedByChoices.SYSTEM,
            monthly_earning=monthly_earning,
        )
        
        if bank_account.platform != BankPlatformChoices.PAYSTACK:
            logger.error(f'Tried to initiate a paystack transfer for a non-paystack bank account for {labeler.username}, skipping payment processing')
            transaction.mark_failed(reason="Tried to initiate a paystack transfer for a non-paystack bank account")
            #TODO: send an email to the labeller telling them that the transfer failed because their primary bank account is not a Nigerian account
            return False
        
        recipient_data = {
            "type": "nuban",
            "name": f"{labeler.username}",
            "account_number": bank_account.account_number,
            "bank_code": bank_account.bank_code,
            "currency": "NGN"
        }
        
        recipient_response = TransferRecipient.create(**recipient_data)
        if not recipient_response.get("status"):
            logger.error(f'Could not initiate transfer for {labeler.username}, skipping payment processing')
            transaction.mark_failed(reason="Could not initiate transfer, please double check the account information and try again.")
            #TODO: send an email to the labeller telling them that the transfer failed because the account information is invalid
            return False
        
        recipient_code = recipient_response.get("data").get("recipient_code")
        
        transfer_data = {
            "source": "balance",
            "reason": "Monthly payment",
            "amount": int(float(ngn_amount) * 100),
            "recipient": recipient_code,
            "reference": reference
        }
        
        transfer_response = paystack.transfer.initiate(**transfer_data)
        if not transfer_response.get("status"):
            logger.error(f'Could not initiate transfer for {labeler.username}, internal paystack error likely due to insufficent balance or invalid account information')
            #TODO: send an email to the labeller telling them that the transfer failed 
            transaction.mark_failed(reason="Could not initiate transfer, account information might be invalid")           
            return False
        
        logger.info(f'Successfully initiated transfer for {labeler.username} with amount {usd_amount}')
        return True
    except Exception as e:
        if transaction:
            transaction.mark_failed(reason=str(e))


@shared_task
def process_single_payment(monthly_earning_id):
    try:
        monthly_earning = MonthlyReviewerEarnings.objects.get(id=monthly_earning_id)

        if monthly_earning.usd_balance <= decimal.Decimal('0.00'):
            logger.info(f'{monthly_earning.reviewer.username} did not earn any money in {monthly_earning.year}-{monthly_earning.month}, skipping payment processing')
            return

        if monthly_earning.release_status in [MonthlyEarningsReleaseStatusChoices.PENDING, MonthlyEarningsReleaseStatusChoices.FAILED]: #only process payments that are either pending or failed
            
            success = initiate_monthly_usd_paystack_transfer(monthly_earning)
            
            monthly_earning.release_status = MonthlyEarningsReleaseStatusChoices.INITIATED if success else MonthlyEarningsReleaseStatusChoices.FAILED
            monthly_earning.save(update_fields=['release_status'])
        else:
            logger.info(f"Monthly earning release status for {monthly_earning.reviewer.username} in {monthly_earning.year}-{monthly_earning.month} is {monthly_earning.release_status}, skipping payment processing")           
            return
    except MonthlyReviewerEarnings.DoesNotExist:
        logger.error(f'Monthly earning {monthly_earning_id} not found, skipping payment processing')
        return
    except Exception as e:
        logger.error(f'Error processing payment for {monthly_earning_id}: {str(e)}', exc_info=True)
        return
    
    

@shared_task
def process_pending_payments():    
    logger.info(f'Processing pending payments for all reviewers')
    
    #get all monthly earnings that are either pending or the previous attempt to release the earnings failed
    pending_monthly_earnings = MonthlyReviewerEarnings.objects.filter(Q(release_status=MonthlyEarningsReleaseStatusChoices.PENDING) | Q(release_status=MonthlyEarningsReleaseStatusChoices.FAILED))
    
    logger.info(f'Found {pending_monthly_earnings.count()} pending monthly earnings.. attempting to process them now')
    
    for earning in pending_monthly_earnings:
        process_single_payment.delay(earning.id)
    
    logger.info(f'Processing pending payments for all reviewers queued successfully')

# @shared_task
# def retry_failed_payments():
#     try:
#         logger.info(f'Retrying all failed payments')
        
#         failed_payments = MonthlyPayment.objects.filter(status=MonthlyPaymentStatusChoices.FAILED)
        
#         logger.info(f'Found {failed_payments.count()} failed payments')
        
#         for payment in failed_payments:
#             process_single_payment.delay(payment.user.id, payment.year, payment.month)
            
#     except Exception as e:
#         logger.error(f'Error retrying failed payments: {str(e)}', exc_info=True)