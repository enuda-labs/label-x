import uuid
from rest_framework import generics, status
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from account.utils import IsReviewer
from common.caching import cache_response_decorator
from common.responses import ErrorResponse, SuccessResponse
from paystackapi.misc import Misc
from paystackapi.paystack import Paystack, TransferRecipient
from django.conf import settings
from rest_framework.response import Response
import logging
from rest_framework.permissions import IsAuthenticated
import decimal

from payment.choices import TransactionStatusChoices
from payment.models import WithdrawalRequest
from payment.serializers import PaystackWithdrawSerializer
from account.models import LabelerEarnings
from payment.utils import convert_usd_to_ngn, find_bank_by_code, request_paystack, verify_paystack_origin
import json
from django.db.models import F

from task.utils import get_labeller_current_month_preview, get_labeller_monthly_history


logger = logging.getLogger('payment.apis')

paystack = Paystack(secret_key=settings.PAYSTACK_SECRET_KEY)


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
        
        withdrawal_request = WithdrawalRequest.objects.create(
            account_number=account_number,
            bank_code=bank_code,
            bank_name=bank.get('name'),
            reference=reference,
            ngn_amount = ngn_amount,
            usd_amount = amount,
            user=request.user
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
            withdrawal_request.status = TransactionStatusChoices.FAILED
            withdrawal_request.save()
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
            withdrawal_request.status = TransactionStatusChoices.FAILED
            withdrawal_request.save()
            error_message = transfer_response.get("message", "FATAL: Unable to initialize transfer, please contact support")
            #TODO: contact an admin and warn them about the error
            return ErrorResponse(message=error_message, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
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
        if earnings.balance >= withdrawal_request.usd_amount:
            earnings.balance = F('balance') - withdrawal_request.usd_amount
            earnings.save(update_fields=['balance'])
        
        withdrawal_request.status = TransactionStatusChoices.SUCCESS
        withdrawal_request.save()
        
        return withdrawal_request
    
    def handle_transfer_failed(self, payload):
        data = payload.get('data')
        reference = data.get('reference')
        
        withdrawal_request = WithdrawalRequest.objects.filter(reference=reference).first()
        if not withdrawal_request:
            return None
        
        withdrawal_request.status = TransactionStatusChoices.FAILED
        withdrawal_request.save()
        
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



class LabellerEarningsView(generics.GenericAPIView):
    """
    View for checking labeller current month earnings
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current month earnings preview for the logged-in labeller"""
        try:
            earnings_preview = get_labeller_current_month_preview(request.user)
            
            return Response({
                'status': 'success',
                'message': 'Current month earnings preview retrieved successfully',
                'data': earnings_preview
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error getting earnings preview for user {request.user.id}: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'detail': f'Failed to get earnings preview: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LabellerEarningsHistoryView(generics.GenericAPIView):
    """
    View for checking labeller earnings history
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get earnings history for the logged-in labeller"""
        try:
            # Get months parameter from query params (default 6)
            months_back = int(request.query_params.get('months', 6))
            months_back = min(max(months_back, 1), 24)  # Limit between 1 and 24 months
            
            earnings_history = get_labeller_monthly_history(request.user, months_back)
            
            return Response({
                'status': 'success',
                'message': f'Earnings history for last {months_back} months retrieved successfully',
                'data': earnings_history
            }, status=status.HTTP_200_OK)
            
        except ValueError:
            return Response({
                'status': 'error',
                'detail': 'Invalid months parameter. Please provide a valid number.'
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error getting earnings history for user {request.user.id}: {str(e)}", exc_info=True)
            return Response({
                'status': 'error',
                'detail': f'Failed to get earnings history: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)