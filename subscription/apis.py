from datetime import timedelta
from django.utils import timezone

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample, OpenApiResponse

from .models import SubscriptionPlan, Subscription, Wallet
from .serializers import (
    SubscriptionPlanSerializer,
    SubscriptionCreateSerializer,
    SubscriptionStatusSerializer,
)


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
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SubscribeToPlanView(generics.CreateAPIView):
    serializer_class = SubscriptionCreateSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Subscribe to a plan using wallet balance",
        request=SubscriptionCreateSerializer,
        responses={
            201: SubscriptionStatusSerializer,
            400: OpenApiResponse(description="Insufficient wallet balance"),
        },
        examples=[
            OpenApiExample(
                "Subscription Request",
                value={"plan_id": 2},
                request_only=True
            ),
            OpenApiExample(
                "Success Response",
                value={
                    "plan": {"id": 2, "name": "Pro", "price": 25.0},
                    "expires_at": "2025-06-12T14:30:00Z",
                    "wallet_balance": 75.0
                },
                response_only=True
            ),
        ]
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan = serializer.validated_data["plan"]
        user = request.user
        wallet = Wallet.objects.get(user=user)

        if wallet.balance < plan.price:
            return Response({"error": "Insufficient wallet balance"}, status=400)

        wallet.balance -= plan.price
        wallet.save()

        expires_at = timezone.now() + timedelta(days=30)
        subscription, _ = Subscription.objects.update_or_create(
            user=user,
            defaults={"plan": plan, "expires_at": expires_at}
        )

        return Response({
            "plan": SubscriptionPlanSerializer(plan).data,
            "expires_at": expires_at,
            "wallet_balance": wallet.balance
        }, status=201)


class CurrentSubscriptionView(generics.RetrieveAPIView):
    serializer_class = SubscriptionStatusSerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Get current user’s active plan and wallet balance",
        responses={
            200: SubscriptionStatusSerializer,
            404: OpenApiResponse(description="No active subscription found"),
        },
        examples=[
            OpenApiExample(
                "Current Plan",
                value={
                    "plan": {"id": 2, "name": "Pro", "price": 25.0},
                    "expires_at": "2025-06-12T14:30:00Z",
                    "wallet_balance": 45.0
                },
                response_only=True
            )
        ]
    )
    def get(self, request, *args, **kwargs):
        try:
            subscription = Subscription.objects.get(user=request.user)
            wallet = Wallet.objects.get(user=request.user)

            return Response({
                "plan": SubscriptionPlanSerializer(subscription.plan).data,
                "expires_at": subscription.expires_at,
                "wallet_balance": wallet.balance
            })
        except Subscription.DoesNotExist:
            return Response({"error": "No active subscription"}, status=404)
