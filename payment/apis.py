import uuid
from django.db import transaction
from account.choices import MonthlyEarningsReleaseStatusChoices, StripeConnectAccountStatusChoices
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

from payment.choices import TransactionStatusChoices, TransactionTypeChoices, WithdrawalRequestInitiatedByChoices
from payment.models import Transaction, WithdrawalRequest
from payment.serializers import PaystackWithdrawSerializer, TransactionSerializer
from account.models import CustomUser, MonthlyReviewerEarnings, UserStripeConnectAccount
from payment.utils import convert_usd_to_ngn, find_bank_by_code, request_paystack, verify_paystack_origin
import json
from django.db.models import F, Sum, Q
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from subscription.models import SubscriptionPlan, UserDataPoints, UserPaymentHistory, UserPaymentStatus, UserSubscription
from task.utils import calculate_static_labeller_monthly_earning, get_labeller_monthly_history, get_unreleased_reviewer_earnings
from datetime import datetime, timedelta
from django.utils import timezone
import stripe


logger = logging.getLogger(__name__)

paystack = Paystack(secret_key=settings.PAYSTACK_SECRET_KEY)


class StripeWebhookListener(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]

    def get_user_and_plan_from_event(self, event):
        event_object = event.get("data", {}).get("object", {})
        customer_email = event_object.get("customer_email")
        price_id = event_object.get("lines").get("data")[0].get("plan").get("id")
        
        try:
            customer = CustomUser.objects.get(email=customer_email)
        except CustomUser.DoesNotExist:
            customer = None
            logger.warning(f"Customer not found for email: {customer_email} at {datetime.now()}")

        subscription_plan = SubscriptionPlan.objects.filter(
            stripe_monthly_plan_id=price_id
        ).first()

        return customer, subscription_plan
    
    def handle_invoice_payment_succeeded(self, event):
        customer, subscription_plan = self.get_user_and_plan_from_event(event)

        if customer and subscription_plan:
            # grant user permissions
            expires_at = timezone.now() + timedelta(days=30)
            try:
                user_subscription = UserSubscription.objects.get(user=customer)
                user_subscription.expires_at = expires_at
                user_subscription.renews_at = expires_at
                user_subscription.plan = subscription_plan
                user_subscription.save(update_fields=['expires_at', 'renews_at', "plan"])
            except UserSubscription.DoesNotExist:
                # create a new subscription for the user
                user_subscription= UserSubscription.objects.create(
                    user=customer,
                    plan = subscription_plan,
                    expires_at=expires_at,
                    renews_at = expires_at,
                )

            user_data_points, created = UserDataPoints.objects.get_or_create(user=customer)
            user_data_points.topup_data_points(subscription_plan.included_data_points)        

            UserPaymentHistory.objects.create(
                user=customer,
                amount=subscription_plan.monthly_fee,
                description=f"Subscription for {subscription_plan.name}",
                status=UserPaymentStatus.SUCCESS,
            )
            logger.info(f"User '{customer.username}' subscribed to plan '{subscription_plan.name}' at {datetime.now()}")

    def handle_customer_subscription_deleted(self, event):
        logger.info(f"Subscription deleted event received at {datetime.now()}")
        # TODO: revoke user permissions
        pass
    
    def handle_connect_account_updated(self, event):
        logger.info(f"Connect account updated event received at {datetime.now()}")
        
        account_data = event.get('data', {}).get('object', {})
        account_id = account_data.get('id')
            
        if not account_id:
            return 
        
        logger.info(f"Account id: {account_id}")
        
        connect_account = UserStripeConnectAccount.objects.filter(account_id=account_id).first()
        if not connect_account:
            return
        
        print('the connect account is', connect_account)
        
        if account_data.get('details_submitted'):
            #user has filled out the onboarding form.
            logger.info(f"User '{connect_account.user.username}' has filled out the onboarding form at {datetime.now()}")
            connect_account.status = StripeConnectAccountStatusChoices.COMPLETED
            connect_account.save(update_fields=['status'])
        else:
            #this means the form has not been filled out yet but the user has already started interacting with the onboarding link
            if connect_account.status == StripeConnectAccountStatusChoices.PENDING:
                logger.info(f"User '{connect_account.user.username}' has started interacting with the onboarding link at {datetime.now()}")
                connect_account.status = StripeConnectAccountStatusChoices.INITIATED
                connect_account.save(update_fields=['status'])
        
        
        if account_data.get('payouts_enabled'):
            logger.info(f"User '{connect_account.user.username}' has enabled payouts at {datetime.now()}")
            connect_account.payouts_enabled = True
            connect_account.save(update_fields=['payouts_enabled'])
   
    def handle_connect_account_deauthorized(self, event):
        logger.info(f"Connect account deauthorized event received at {datetime.now()}")
        
        account_id = event.get('account')
        if not account_id:
            return 
        
        connect_account = UserStripeConnectAccount.objects.filter(account_id=account_id).first()
        if not connect_account:
            return
        
        connect_account.status = StripeConnectAccountStatusChoices.DISABLED
        connect_account.save(update_fields=['status'])
    
    def handle_transfer_created(self, event):
        """Handle Stripe transfer.created webhook"""
        logger.info(f"Stripe transfer created event received at {datetime.now()}")
        
        transfer_data = event.get('data', {}).get('object', {})
        transfer_id = transfer_data.get('id')
        status = transfer_data.get('status')
        
        if not transfer_id:
            return
        
        # Find the withdrawal request by transfer ID
        withdrawal_request = WithdrawalRequest.objects.filter(reference=transfer_id).first()
        if not withdrawal_request:
            logger.warning(f"No withdrawal request found for transfer ID: {transfer_id}")
            return
        
        logger.info(f"Transfer created for {withdrawal_request.transaction.user.username}, transfer ID: {transfer_id}, status: {status}")
        
        # Handle initial transfer status
        if status == 'pending':
            logger.info(f"Transfer is pending for {withdrawal_request.transaction.user.username}")
            withdrawal_request.transaction.status = TransactionStatusChoices.PROCESSING
            withdrawal_request.transaction.save(update_fields=['status'])
            # Transfer is created and pending - no action needed yet
        elif status == 'paid':
            # Transfer completed immediately
            logger.info(f"Transfer completed immediately for {withdrawal_request.transaction.user.username}")
            withdrawal_request.transaction.mark_success()

            # Deduct balance from monthly earnings
            if withdrawal_request.monthly_earning:
                monthly_earning = withdrawal_request.monthly_earning
                monthly_earning.deduct_balance(withdrawal_request.transaction.usd_amount)
                monthly_earning.release_status = MonthlyEarningsReleaseStatusChoices.RELEASED
                monthly_earning.save(update_fields=['release_status'])
        elif status == 'failed':
            # Transfer failed immediately
            logger.error(f"Transfer failed immediately for {withdrawal_request.transaction.user.username}")
            withdrawal_request.transaction.mark_failed(reason="Stripe transfer failed")

            if withdrawal_request.monthly_earning:
                monthly_earning = withdrawal_request.monthly_earning
                monthly_earning.release_status = MonthlyEarningsReleaseStatusChoices.FAILED
                monthly_earning.save(update_fields=['release_status'])
    
    
    def handle_balance_available(self, event):
        account_id = event.get("account")
        if not account_id:
            return 
        
        event_object = event.get("data", {}).get("object", {})
        available = event_object.get("available")
        
        usd_balance_obj = None
        if isinstance(available, list):
            for x in available:
                if x.get("currency") == "usd":
                    usd_balance_obj = x
                    break
        
        if not usd_balance_obj:
            return
        
        usd_amount = usd_balance_obj.get("amount")
        if not usd_amount:
            return
        
        # Create a Stripe payout to the connected account's default external account
        payout = stripe.Payout.create(
            amount=int(usd_amount),  # Stripe expects amount in cents
            currency='usd',
            description="Payout to connected account's default external account",
            stripe_account=account_id
        )
        logger.info(f"Stripe payout created for account {account_id} with amount {usd_amount}, payout ID: {payout.id}")
    
    def handle_transfer_updated(self, event):
        """Handle Stripe transfer.updated webhook - handles status changes from pending to paid/failed"""
        # TODO TO BE REVIEWED
        # logger.info(f"Stripe transfer updated event received at {datetime.now()}")
        
        # transfer_data = event.get('data', {}).get('object', {})
        # transfer_id = transfer_data.get('id')
        # status = transfer_data.get('status')
        
        # if not transfer_id:
        #     return
        
        # # Find the withdrawal request by transfer ID
        # withdrawal_request = WithdrawalRequest.objects.filter(reference=transfer_id).first()
        # if not withdrawal_request:
        #     logger.warning(f"No withdrawal request found for transfer ID: {transfer_id}")
        #     return
        
        # # Only process if transaction is still pending (avoid duplicate processing)
        # if withdrawal_request.transaction.status != TransactionStatusChoices.PENDING:
        #     logger.info(f"Transfer {transfer_id} already processed, skipping update")
        #     return
        
        # if status == 'paid':
        #     logger.info(f"Transfer completed for {withdrawal_request.transaction.user.username}")
        #     withdrawal_request.transaction.mark_success()
            
        #     # call the payout API to payout the funds to the labeller's bank account
        #     try:
        #         payout = stripe.Payout.create(
        #             amount=int(withdrawal_request.transaction.usd_amount * 100),
        #             currency='usd',
        #             description="Payout to bank account",
        #             stripe_account=withdrawal_request.transaction.user.stripe_connect_account.account_id
        #         )
        #         logger.info(f"Payout created for {withdrawal_request.transaction.user.username}, payout ID: {payout.id}")
        #     except stripe.error.StripeError as e:
        #         logger.error(
        #             f"Stripe payout failed for {withdrawal_request.transaction.user.username}: {str(e)}",
        #             exc_info=True
        #         )
                
        # elif status == 'failed':
        #     logger.error(f"Transfer failed for {withdrawal_request.transaction.user.username}")
        #     withdrawal_request.transaction.mark_failed(reason="Stripe transfer failed")
            
        #     if withdrawal_request.monthly_earning:
        #         monthly_earning = withdrawal_request.monthly_earning
        #         monthly_earning.release_status = MonthlyEarningsReleaseStatusChoices.FAILED
        #         monthly_earning.save(update_fields=['release_status'])
    
    def validate_origin(self, request, endpoint_secret):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {str(e)} at {datetime.now()}")
            return False, "Invalid webhook payload"
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {str(e)} at {datetime.now()}")
            return False, "Invalid webhook signature"
        return True, event
    
    def post(self, request):
        # payload = request.body
        # sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        # try:
        #     event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        # except ValueError as e:
        #     logger.error(f"Invalid webhook payload: {str(e)} at {datetime.now()}")
        #     return ErrorResponse(message="Invalid webhook payload", status=400)
        # except stripe.error.SignatureVerificationError as e:
        #     logger.error(f"Invalid webhook signature: {str(e)} at {datetime.now()}")
        #     return ErrorResponse(status=400, message="Invalid webhook signature")
        
        success, event = self.validate_origin(request, endpoint_secret)
        if not success:
            success, event = self.validate_origin(request, settings.STRIPE_CONNECT_WEBHOOK_SECRET)
            if not success:
                return ErrorResponse(message="Invalid webhook signature", status=status.HTTP_400_BAD_REQUEST)

        event_type = event.get("type")
        logger.info(f"Received Stripe webhook event: {event_type} at {datetime.now()}")
        print("Received Stripe webhook event: ", event_type, event)

        if event_type == "invoice.payment_succeeded":
            self.handle_invoice_payment_succeeded(event)
            
        if event_type == "customer.subscription.deleted":
            self.handle_customer_subscription_deleted(event)
            
        if event_type == "account.updated":
            self.handle_connect_account_updated(event)
            
        if event_type == "account.application.deauthorized":
            self.handle_connect_account_deauthorized(event)
            
        if event_type == "transfer.created":
            self.handle_transfer_created(event)
            
        if event_type == "transfer.updated":
            self.handle_transfer_updated(event)
        
        # if event_type == "balance.available":
        #     self.handle_balance_available(event)
        if event_type == "payout.paid":
            logger.info(f"Payout completed successfully for connected account {event.get('account')}")
            # TODO SEND EMAIL TO NOTIFY
        elif event_type == "payout.failed":
            logger.error(f"Payout failed for connected account {event.get('account')}: {event}")
            # TODO SEND EMAIL TO NOTIFY OF PAYMENT FAILURE

        
        return SuccessResponse(message="OK")

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
        
        if WithdrawalRequest.objects.filter(transaction__user=request.user, transaction__status=TransactionStatusChoices.PENDING, initiated_by=WithdrawalRequestInitiatedByChoices.USER).exists():
            return ErrorResponse(message="You already have a pending withdrawal request, please wait for it to be processed or contact support", status=status.HTTP_400_BAD_REQUEST)
                
        user_total_earnings = get_unreleased_reviewer_earnings(request.user)
        
        account_number = serializer.validated_data.get('account_number')
        bank_code = serializer.validated_data.get('bank_code')
        amount = serializer.validated_data.get('amount')
        
        ngn_amount = convert_usd_to_ngn(amount)
        
        #ensure that the labeler has enough in his balance
        if user_total_earnings < amount: 
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
            transaction=transaction,
            initiated_by=WithdrawalRequestInitiatedByChoices.USER,
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
            "recipient": recipient_code,
            "reference": reference
        }
        
        transfer_response = paystack.transfer.initiate(**transfer_data)
        if not transfer_response.get('status', False):
            transaction.mark_failed()
            error_message = transfer_response.get("message", "FATAL: Unable to initialize transfer, please contact support")
            #TODO: contact an admin and warn them about the error
            return ErrorResponse(message=error_message, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        return SuccessResponse(message="Withdrawal request initiated successfully, your funds will be available in your bank account in a few minutes")

class PaystackWebhookListener(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    
    @method_decorator(csrf_exempt, name='dispatch')
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def handle_transfer_success(self, payload):
        data = payload.get('data')
        
        reference = data.get('reference')
        
        withdrawal_request = WithdrawalRequest.objects.select_related('transaction', 'monthly_earning').filter(reference=reference).first()
        
        if not withdrawal_request or withdrawal_request.is_user_balance_deducted:
            withdrawal_request.transaction.mark_failed()
            return None
        
        if withdrawal_request.initiated_by == WithdrawalRequestInitiatedByChoices.USER:
            user_earnings = MonthlyReviewerEarnings.objects.filter(Q(reviewer=withdrawal_request.transaction.user) & ~Q(release_status=MonthlyEarningsReleaseStatusChoices.RELEASED)).order_by('-usd_balance')
            total_earnings = user_earnings.aggregate(total_earnings=Sum('total_earnings_usd'))['total_earnings']
            
            if total_earnings < withdrawal_request.transaction.usd_amount:
                withdrawal_request.transaction.mark_failed()
                return withdrawal_request
            
            amount_to_deduct = withdrawal_request.transaction.usd_amount
            
            for earning in user_earnings:
                if amount_to_deduct <= 0:
                    break
                
                if earning.usd_balance >= amount_to_deduct:
                    earning.deduct_balance(amount_to_deduct)
                    amount_to_deduct = 0
                else:
                    earning.deduct_balance(earning.usd_balance)
                    amount_to_deduct -= earning.usd_balance
                    
            withdrawal_request.transaction.mark_success()
            return withdrawal_request
        

        if withdrawal_request.initiated_by == WithdrawalRequestInitiatedByChoices.SYSTEM:
            if not withdrawal_request.monthly_earning:
                withdrawal_request.transaction.mark_failed()
                return None
            
            monthly_earning = withdrawal_request.monthly_earning
            
            if monthly_earning.usd_balance < withdrawal_request.transaction.usd_amount:
                withdrawal_request.transaction.mark_failed()
                
                monthly_earning.release_status = MonthlyEarningsReleaseStatusChoices.FAILED
                monthly_earning.save(update_fields=['release_status'])
                return None
            
            try:
                with transaction.atomic():
                    monthly_earning.deduct_balance(withdrawal_request.transaction.usd_amount)
                    monthly_earning.release_status = MonthlyEarningsReleaseStatusChoices.RELEASED
                    monthly_earning.save(update_fields=['release_status'])
            except Exception as e:
                withdrawal_request.transaction.mark_failed()
                return withdrawal_request
            
        return withdrawal_request
    
    def handle_transfer_failed(self, payload):
        data = payload.get('data')
        reference = data.get('reference')
        
        withdrawal_request = WithdrawalRequest.objects.select_related('transaction', 'monthly_earning').filter(reference=reference).first()
        if not withdrawal_request:
            return None
        
        if withdrawal_request.initiated_by == WithdrawalRequestInitiatedByChoices.SYSTEM:
            if not withdrawal_request.monthly_earning:
                withdrawal_request.transaction.mark_failed()
                return None
            
            monthly_earning = withdrawal_request.monthly_earning
            
            #if the user's balance was previously deducted and the transfer failed, we need to topup the balance
            if withdrawal_request.is_user_balance_deducted and withdrawal_request.transaction.status == TransactionStatusChoices.PENDING:
                monthly_earning.topup_balance(withdrawal_request.transaction.usd_amount, increment_total_earnings=False)
                
            withdrawal_request.transaction.mark_failed()
            monthly_earning.release_status = MonthlyEarningsReleaseStatusChoices.FAILED
            monthly_earning.save(update_fields=['release_status'])
            return withdrawal_request
    
    def post(self, request, *args, **kwargs):   
        logger.info(f"PAYSTACK WEBHOOK RECEIVED")
        is_valid_origin = verify_paystack_origin(request)
        
                
        if not is_valid_origin:
            return ErrorResponse(message="Invalid origin", status=status.HTTP_400_BAD_REQUEST)
        
        payload = json.loads(request.body)
        event_type = payload.get('event')
        
        print("EVENT TYPE", event_type)
        
        if event_type == 'transfer.success':
            logger.info(f"Received transfer.success webhook")
            self.handle_transfer_success(payload)
        
        if event_type == 'transfer.failed':
            logger.info(f"Received transfer.failed webhook")
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
            now = timezone.now()
            earnings = calculate_static_labeller_monthly_earning(request.user, now.year, now.month)
            
            if now.month == 12:
                next_month_start = timezone.make_aware(datetime(now.year + 1, 1, 1)) if timezone.is_aware(now) else datetime(now.year + 1, 1, 1)
            else:
                next_month_start = timezone.make_aware(datetime(now.year, now.month + 1, 1)) if timezone.is_aware(now) else datetime(now.year, now.month + 1, 1)
                            
            return Response({
                'status': 'success',
                'message': 'Current month earnings preview retrieved successfully',
                'data': {
                    "amount": earnings,
                    "current_month": now.strftime("%B %Y"),
                    "days_left_in_month": (next_month_start - now).days
                }
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
        
        logger.info(f"User '{request.user.username}' fetching earnings history at {datetime.now()}")
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