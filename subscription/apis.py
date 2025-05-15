from datetime import timedelta
from django.utils import timezone

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse
import stripe.error

from account.models import CustomUser
from common.responses import ErrorResponse, SuccessResponse, format_first_error

from .models import SubscriptionPlan, UserSubscription, Wallet
from .serializers import (
    InitializerSubscriptionSerializer,
    SubscriptionPlanSerializer,
    SubscribeRequestSerializer,
    SubscriptionStatusSerializer,
)

import stripe
import json
from django.conf import settings


class StripeWebhookListener(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    
    def get_user_and_plan_from_event(self, event):
        event_object = event.get('data', {}).get('object', {})
        
        customer_email = event_object.get('customer_email')
        
        price_id = event_object.get('lines').get('data')[0].get('plan').get('id')
        try:
            customer = CustomUser.objects.get(email=customer_email)
        except CustomUser.DoesNotExist:
            customer= None
        
        subscription_plan = SubscriptionPlan.objects.filter(stripe_monthly_plan_id=price_id).first()
        
        return customer, subscription_plan

        
    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except ValueError as e:
            return ErrorResponse(message="Error")
        except stripe.error.SignatureVerificationError as e:
            return ErrorResponse(status=400)

        event_type = event.get("type")
                
        if event_type == "invoice.payment_succeeded":            
            customer, subscription_plan = self.get_user_and_plan_from_event(event)
            
            if customer and subscription_plan:
                #grant user permissions
                expires_at = timezone.now() + timedelta(days=30)
                UserSubscription.objects.update_or_create(
                    user=customer, defaults={
                        "plan": subscription_plan,
                        "expires_at": expires_at,
                        "renews_at": expires_at
                    }
                )
                print('user subscribed successfully')
                
            
        if event_type == "customer.subscription.deleted":
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
            return Response({"error": "Insufficient wallet balance"}, status=400)

        wallet.balance -= plan.monthly_fee
        wallet.save()

        expires_at = timezone.now() + timedelta(days=30)
        subscription, _ = SubscriptionPlan.objects.update_or_create(
            user=user, defaults={"plan": plan, "expires_at": expires_at}
        )

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
            return ErrorResponse(message=format_first_error(serializer.errors), data=serializer.errors)
        
        
        subscription_plan = serializer.validated_data.get('subscription_plan')
        
        #checking if admin has set a price id for the chosen plan
        stripe_monthly_price_id= getattr(subscription_plan, "stripe_monthly_plan_id", None)
        if not stripe_monthly_price_id:
            return ErrorResponse(message="A price id has not been configured for this plan, please contact admin support")
            

        # TODO: use correct redirect urls and price id
        try:
            session = stripe.checkout.Session.create(
                success_url="https://google.com",
                cancel_url="https://google.com",
                mode="subscription",
                customer_email=request.user.email,
                line_items=[{"price": stripe_monthly_price_id, "quantity": 1}],
            )
            return SuccessResponse(data={"payment_url": session.url})
        except Exception as e:
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
            subscription = UserSubscription.objects.get(user=request.user)
            wallet = Wallet.objects.get(user=request.user)
            return Response(
                {
                    "plan": SubscriptionPlanSerializer(subscription.plan).data,
                    "wallet_balance": wallet.balance,
                    "subscribed_at": subscription.subscribed_at,
                    "expires_at": subscription.expires_at,
                    "request_balance": subscription.plan.included_requests
                    - subscription.requests_used,
                }
            )
        except UserSubscription.DoesNotExist:
            return Response({"error": "No active subscription found"}, status=404)
