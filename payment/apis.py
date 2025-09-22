import uuid
from django.db import transaction
from rest_framework import generics, status
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from account.utils import IsReviewer
from common.caching import cache_response_decorator
from common.responses import ErrorResponse, SuccessResponse
from paystackapi.misc import Misc
from paystackapi.paystack import Paystack, TransferRecipient
from django.conf import settings
import logging
from rest_framework.permissions import IsAuthenticated
import decimal

from payment.choices import TransactionStatusChoices, TransactionTypeChoices
from payment.models import Transaction, WithdrawalRequest
from payment.serializers import PaystackWithdrawSerializer, TransactionSerializer
from account.models import LabelerEarnings
from payment.utils import convert_usd_to_ngn, find_bank_by_code, request_paystack, verify_paystack_origin
import json
from django.db.models import F
logger = logging.getLogger('payment.apis')

paystack = Paystack(secret_key=settings.PAYSTACK_SECRET_KEY)

class FetchUserTransactionHistoryView(generics.ListAPIView):
    serializer_class = TransactionSerializer
    def get_queryset(self):
        return Transaction.objects.filter(user=self.request.user)
    
    @cache_response_decorator('user_transaction_history', cache_timeout=60 * 60 * 24, per_user=True)
    @extend_schema(summary="Fetch the transaction history for the currently logged in user")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class InitiateLabelerWithdrawalView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated | IsReviewer]
    serializer_class = PaystackWithdrawSerializer
    
    def get_client_paystack_balance(self):
        response = request_paystack('/balance')
        
        if response.error:
            #TODO: contact an admin
            return None

        return response.body.get("data")[0].get("balance")
    
    @extend_schema(summary="Initiate a withdrawal request to a labeler's bank account")
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return ErrorResponse(message=serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        earnings, _ = LabelerEarnings.objects.get_or_create(labeler=request.user)
        
        account_number = serializer.validated_data.get('account_number')
        bank_code = serializer.validated_data.get('bank_code')
        amount = serializer.validated_data.get('amount')
        
        ngn_amount = convert_usd_to_ngn(amount)
        
        #ensure that the labeler has enough in his balance
        if earnings.balance < amount: 
            return ErrorResponse(message="You don't have enough funds to withdraw this amount", status=status.HTTP_400_BAD_REQUEST)
        
        bank = find_bank_by_code(bank_code)
        if not bank:
            return ErrorResponse(message="Bank not supported", status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        
        client_balance = self.get_client_paystack_balance()
        if not client_balance:
            return ErrorResponse(message="Error fetching client balance, please try again later", status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        reference = str(uuid.uuid4())
        
        transaction = Transaction.objects.create(
            user=request.user,
            usd_amount=amount,
            ngn_amount=ngn_amount,
            transaction_type=TransactionTypeChoices.WITHDRAWAL,
            description="Withdrawal to bank account",
        )
        
        withdrawal_request = WithdrawalRequest.objects.create(
            account_number=account_number,
            bank_code=bank_code,
            bank_name=bank.get('name'),
            reference=reference,
            transaction=transaction
        )
        
        if decimal.Decimal(client_balance) < ngn_amount:
            #TODO: contact an admin and warn them about low balance
            return ErrorResponse(message="Your withdrawal request cannot be processed at this moment, please try again later or contact support ", status=status.HTTP_503_SERVICE_UNAVAILABLE)
        
        recipient_data = {
            "type": "nuban",
            "name": f"{request.user.username}",
            "account_number": account_number,
            "bank_code": bank_code,
            "currency": "NGN"
        }
        
        
        recipient_response = TransferRecipient.create(**recipient_data)
        if not recipient_response.get("status"):  
            transaction.mark_failed()
            return ErrorResponse(message="Could not initiate transfer, please double check the account information and try again.", status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        recipient_code = recipient_response.get("data").get("recipient_code")
        transfer_data = {
            "source": "balance",
            "reason": "Withdrawal to bank account",
            "amount": int(float(ngn_amount) * 100),
            "recipient": recipient_code
        }
        
        transfer_response = paystack.transfer.initiate(**transfer_data)
        if not transfer_response.get('status', False):
            transaction.mark_failed()
            error_message = transfer_response.get("message", "FATAL: Unable to initialize transfer, please contact support")
            #TODO: contact an admin and warn them about the error
            return ErrorResponse(message=error_message, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        
        earnings.deduct_balance(withdrawal_request.transaction.usd_amount, create_transaction=False)
        withdrawal_request.is_user_balance_deducted = True
        withdrawal_request.save(update_fields=['is_user_balance_deducted'])
        
        return SuccessResponse(message="Withdrawal request initiated successfully, your funds will be available in your bank account in a few minutes")



class PaystackWebhookListener(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    
    def handle_transfer_success(self, payload):
        data = payload.get('data')
        
        reference = data.get('reference')
        
        withdrawal_request = WithdrawalRequest.objects.filter(reference=reference).first()
        if not withdrawal_request:
            return None
        
        earnings, _ = LabelerEarnings.objects.get_or_create(labeler=withdrawal_request.user)
        
        try:
            with transaction.atomic():
                if not withdrawal_request.is_user_balance_deducted:
                    if earnings.balance >= withdrawal_request.transaction.usd_amount:
                        
                        earnings.deduct_balance(withdrawal_request.transaction.usd_amount, create_transaction=False)
            
                        withdrawal_request.is_user_balance_deducted = True
                        withdrawal_request.save(update_fields=['is_user_balance_deducted'])
                        
                        withdrawal_request.transaction.mark_success()
                        
                    else:
                        withdrawal_request.transaction.mark_failed()
                        return withdrawal_request
        except Exception as e:
            withdrawal_request.transaction.mark_failed()
            return withdrawal_request

        return withdrawal_request
    
    def handle_transfer_failed(self, payload):
        data = payload.get('data')
        reference = data.get('reference')
        
        withdrawal_request = WithdrawalRequest.objects.filter(reference=reference).first()
        if not withdrawal_request:
            return None
        
        #if the user's balance was previously deducted and the transfer failed, we need to topup the balance
        if withdrawal_request.is_user_balance_deducted and withdrawal_request.transaction.status == TransactionStatusChoices.PENDING:
            earnings, _ = LabelerEarnings.objects.get_or_create(labeler=withdrawal_request.user)
            earnings.topup_balance(withdrawal_request.transaction.usd_amount, ngn_amount=withdrawal_request.transaction.ngn_amount)
            
        withdrawal_request.transaction.mark_failed()
        return withdrawal_request
    
    def post(self, request, *args, **kwargs):        
        is_valid_origin = verify_paystack_origin(request)
        if not is_valid_origin:
            return ErrorResponse(message="Invalid origin", status=status.HTTP_400_BAD_REQUEST)
        
        payload = json.loads(request.body)
        event_type = payload.get('event')
        
        if event_type == 'transfer.success':
            self.handle_transfer_success(payload)
        
        if event_type == 'transfer.failed':
            self.handle_transfer_failed(payload)
        
        return SuccessResponse(message="OK Response")

class GetPaystackBankCodesView(generics.ListAPIView):
    
    @cache_response_decorator('paystack_bank_codes', cache_timeout=60 * 60 * 24)
    def list(self, request, *args, **kwargs):
        response = Misc.list_banks()
        if response.get("status"):
            return SuccessResponse(data=response.get("data"))
        return ErrorResponse(message="Error fetching banks")
    
    @extend_schema(summary="Get all the banks that paystack supports for withdrawal")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)