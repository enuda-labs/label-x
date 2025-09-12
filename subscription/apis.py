from datetime import timedelta
import decimal
from django.utils import timezone
import logging
from datetime import datetime

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
import stripe.error

from account.models import CustomUser
from common.responses import ErrorResponse, SuccessResponse, format_first_error
from subscription.utils import get_request_origin

from .models import (
    SubscriptionPlan,
    UserDataPoints,
    UserPaymentHistory,
    UserPaymentStatus,
    UserSubscription,
    Wallet,
)
from .serializers import (
    InitializerSubscriptionSerializer,
    SubscriptionPlanSerializer,
    SubscribeRequestSerializer,
    SubscriptionStatusSerializer,
    UserDataPointsSerializer,
    UserPaymentHistorySerializer,
)

import stripe
import json
from django.conf import settings

logger = logging.getLogger('subscription.apis')
from django.db.models import F

class GetUserPaymentHistoryView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserPaymentHistorySerializer

    @extend_schema(
        summary="Get the payment history list for the currently logged in user"
    )
    def get_queryset(self):
        logger.info(f"User '{self.request.user.username}' fetching payment history at {datetime.now()}")
        return UserPaymentHistory.objects.filter(user=self.request.user)


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

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {str(e)} at {datetime.now()}")
            return ErrorResponse(message="Error")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {str(e)} at {datetime.now()}")
            return ErrorResponse(status=400)

        event_type = event.get("type")
        logger.info(f"Received Stripe webhook event: {event_type} at {datetime.now()}")

        if event_type == "invoice.payment_succeeded":
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

        if event_type == "customer.subscription.deleted":
            logger.info(f"Subscription deleted event received at {datetime.now()}")
            # TODO: revoke user permissions
            pass

        # print("stripe webhook was called", request.data.get("type"))
        return SuccessResponse(message="")


class ListSubscriptionPlansView(generics.ListAPIView):
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="List all available subscription plans",
        responses={200: SubscriptionPlanSerializer(many=True)},
        examples=[
            OpenApiExample(
                "Plans Example",
                value=[
                    {"id": 1, "name": "Starter", "price": 10.0},
                    {"id": 2, "name": "Pro", "price": 25.0},
                    {"id": 3, "name": "Enterprise", "price": 100.0},
                ],
                response_only=True,
            )
        ],
    )
    def get(self, request, *args, **kwargs):
        logger.info(f"User '{request.user.username if request.user.is_authenticated else 'Anonymous'}' fetched subscription plans at {datetime.now()}")
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({"status": "success", "detail": serializer.data})


class SubscribeToPlanView(generics.CreateAPIView):
    serializer_class = SubscribeRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Subscribe to a plan using wallet balance",
        request=SubscribeRequestSerializer,
        responses={
            201: SubscriptionStatusSerializer,
            400: OpenApiResponse(description="Insufficient wallet balance"),
        },
        examples=[
            OpenApiExample(
                "Subscription Request", value={"plan_id": 2}, request_only=True
            ),
            OpenApiExample(
                "Success Response",
                value={
                    "plan": {"id": 2, "name": "Pro", "price": 25.0},
                    "expires_at": "2025-06-12T14:30:00Z",
                    "wallet_balance": 75.0,
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan = serializer.validated_data["plan"]
        user = request.user
        wallet = Wallet.objects.get(user=user)

        if wallet.balance < plan.monthly_fee:
            logger.warning(f"User '{user.username}' attempted subscription with insufficient balance. Required: {plan.monthly_fee}, Available: {wallet.balance} at {datetime.now()}")
            return Response({"error": "Insufficient wallet balance"}, status=400)

        wallet.balance -= plan.monthly_fee
        wallet.save()

        expires_at = timezone.now() + timedelta(days=30)
        subscription, _ = SubscriptionPlan.objects.update_or_create(
            user=user, defaults={"plan": plan, "expires_at": expires_at}
        )

        logger.info(f"User '{user.username}' subscribed to plan '{plan.name}' using wallet balance at {datetime.now()}")
        return Response(
            {
                "status": "success",
                "detail": {
                    "plan": SubscriptionPlanSerializer(plan).data,
                    "expires_at": expires_at,
                    "wallet_balance": wallet.balance,
                },
            },
            status=201,
        )


class InitializeStripeSubscription(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = InitializerSubscriptionSerializer

    @extend_schema(
        summary="Get the payment url for a stripe subscription",
    )
    def post(self, request):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Invalid subscription initialization request by '{request.user.username}': {serializer.errors} at {datetime.now()}")
            return ErrorResponse(
                message=format_first_error(serializer.errors), data=serializer.errors
            )

        subscription_plan = serializer.validated_data.get("subscription_plan")

        # checking if admin has set a price id for the chosen plan
        stripe_monthly_price_id = getattr(
            subscription_plan, "stripe_monthly_plan_id", None
        )
        if not stripe_monthly_price_id:
            logger.error(f"Missing Stripe price ID for plan '{subscription_plan.name}' requested by '{request.user.username}' at {datetime.now()}")
            return ErrorResponse(
                message="A price id has not been configured for this plan, please contact admin support"
            )

        callback_url = f"{get_request_origin(request)}/client/overview"      
        try:
            session = stripe.checkout.Session.create(
                success_url=callback_url,
                cancel_url=callback_url,
                mode="subscription",
                customer_email=request.user.email,
                line_items=[{"price": stripe_monthly_price_id, "quantity": 1}],
            )
            logger.info(f"User '{request.user.username}' initialized Stripe subscription for plan '{subscription_plan.name}' at {datetime.now()}")
            return SuccessResponse(data={"payment_url": session.url})
        except Exception as e:
            logger.error(f"Stripe subscription initialization failed for user '{request.user.username}': {str(e)} at {datetime.now()}")
            return ErrorResponse(
                message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CurrentSubscriptionView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Get current user's subscription status",
        responses={
            200: SubscriptionStatusSerializer,
            404: OpenApiResponse(description="No active subscription found"),
        },
    )
    def get(self, request):
        try:
            subscription = UserSubscription.objects.filter(user=request.user).order_by('-subscribed_at').first()
            if not subscription:
                return ErrorResponse(message="No subscription found", status=status.HTTP_404_NOT_FOUND)
            wallet, created = Wallet.objects.get_or_create(user=request.user)
            logger.info(f"User '{request.user.username}' fetched current subscription status at {datetime.now()}")
            
            user_data_points, created = UserDataPoints.objects.get_or_create(user=request.user)
            return Response(
                {
                    "plan": SubscriptionPlanSerializer(subscription.plan).data,
                    "wallet_balance": wallet.balance,
                    "subscribed_at": subscription.subscribed_at,
                    "expires_at": subscription.expires_at,
                    "request_balance": subscription.plan.included_requests
                    - subscription.requests_used,
                    "user_data_points": UserDataPointsSerializer(user_data_points).data
                }
            )
        except UserSubscription.DoesNotExist:
            logger.warning(f"No active subscription found for user '{request.user.username}' at {datetime.now()}")
            return Response({"error": "No active subscription found"}, status=404)
