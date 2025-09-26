import decimal
import uuid
from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from account.choices import BankPlatformChoices
from account.models import CustomUser, UserBankAccount
from payment.choices import MonthlyPaymentStatusChoices, TransactionTypeChoices
from payment.utils import convert_usd_to_ngn
from task.models import ManualReviewSession
from payment.models import MonthlyPayment, Transaction
from task.utils import calculate_labeller_monthly_earning
from paystackapi.paystack import Paystack, TransferRecipient
from django.conf import settings
import logging

logger = logging.getLogger('default')


paystack = Paystack(secret_key=settings.PAYSTACK_SECRET_KEY)


def initiate_monthly_usd_paystack_transfer(usd_amount, labeler):
    try:
        logger.info(f'Initiating monthly USD paystack transfer for {labeler.username} with amount {usd_amount}')
        
        ngn_amount = convert_usd_to_ngn(usd_amount)
        logger.info(f'Converted USD to NGN for {labeler.username} with amount {usd_amount} is {ngn_amount}')
        
        reference = str(uuid.uuid4())
        
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
        
        if bank_account.platform != BankPlatformChoices.PAYSTACK:
            logger.error(f'Tried to initiate a paystack transfer for a non-paystack bank account for {labeler.username}, skipping payment processing')
            transaction.mark_failed(reason="Tried to initiate a paystack transfer for a non-paystack bank account")
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
            return False
        
        recipient_code = recipient_response.get("data").get("recipient_code")
        
        transfer_data = {
            "source": "balance",
            "reason": "Monthly payment",
            "amount": int(float(ngn_amount) * 100),
            "recipient": recipient_code
        }
        
        transfer_response = paystack.transfer.initiate(**transfer_data)
        if not transfer_response.get("status"):
            logger.error(f'Could not initiate transfer for {labeler.username}, internal paystack error likely due to insufficent balance or invalid account information')
            transaction.mark_failed(reason="Could not initiate transfer, please double check the account information and try again.")
            return False
        
        logger.info(f'Successfully initiated transfer for {labeler.username} with amount {usd_amount}')
        transaction.mark_success()
        return True
    except Exception as e:
        if transaction:
            transaction.mark_failed(reason=str(e))


@shared_task
def process_single_payment(labeler_id, year, month):
    try:
        labeler= CustomUser.objects.get(id=labeler_id)
        
        #check if we have already tried to pay the user for that month
        monthly_payment, created = MonthlyPayment.objects.get_or_create(user=labeler, year=year, month=month, defaults={'usd_amount': 0, 'status': MonthlyPaymentStatusChoices.PENDING})
        
        if monthly_payment.status != MonthlyPaymentStatusChoices.SUCCESS: #only process payments that are either pending or failed
            earning = calculate_labeller_monthly_earning(labeler, year, month) if created else monthly_payment.usd_amount
            logger.info(f'Calculated earning for {labeler.username} in {year}-{month} is {earning}')
            
            if earning <= decimal.Decimal('0.00'):
                monthly_payment.status = MonthlyPaymentStatusChoices.SUCCESS
                monthly_payment.save(update_fields=['status'])
                return
            success = initiate_monthly_usd_paystack_transfer(earning, labeler)
            
            monthly_payment.status = MonthlyPaymentStatusChoices.SUCCESS if success else MonthlyPaymentStatusChoices.FAILED
            monthly_payment.usd_amount = earning
            monthly_payment.save(update_fields=['status', 'usd_amount'])
            
            
    except CustomUser.DoesNotExist:
        logger.error(f'Labeler {labeler_id} not found, skipping payment processing')
        return
    
    

@shared_task
def process_pending_payments():
    #get all the labellers who had at least one manual review session in the current month
    
    now = timezone.now()
    logger.info(f'Processing pending payments for {now.year}-{now.month}')
    
    today = now.date()
    
    tomorrow = today + timedelta(days=1)
    if tomorrow.day == 1:
        #if tomorrow is the first day of the month, then we need to credit the labellers
    
        #the all the reviewers who labeled tasks in the current month
        labeler_ids = ManualReviewSession.objects.filter(created_at__month=now.month, created_at__year=now.year).values_list('labeller', flat=True).distinct()
        
        for labeler_id in labeler_ids:
            process_single_payment.delay(labeler_id, now.year, now.month)
        
    logger.info(f'Processing pending payments for {now.year}-{now.month} queued successfully')

@shared_task
def retry_failed_payments():
    try:
        logger.info(f'Retrying all failed payments')
        
        failed_payments = MonthlyPayment.objects.filter(status=MonthlyPaymentStatusChoices.FAILED)
        
        logger.info(f'Found {failed_payments.count()} failed payments')
        
        for payment in failed_payments:
            process_single_payment.delay(payment.user.id, payment.year, payment.month)
            
    except Exception as e:
        logger.error(f'Error retrying failed payments: {str(e)}', exc_info=True)