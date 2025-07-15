from rest_framework import serializers
from .models import SubscriptionPlan, UserPaymentHistory, UserSubscription, Wallet


class UserPaymentHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPaymentHistory
        fields = "__all__"


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ["id", "name", "monthly_fee", "cost_per_extra_request", 'included_data_points']


class UserSubscriptionSerializer(serializers.ModelSerializer):
    plan = SubscriptionPlanSerializer()

    class Meta:
        model = UserSubscription
        fields = ["plan", "subscribed_at", "expires_at", "request_balance"]


class InitializerSubscriptionSerializer(serializers.Serializer):
    subscription_plan = serializers.IntegerField()

    def validate_subscription_plan(self, value):
        try:
            plan = SubscriptionPlan.objects.get(id=value)
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError("Invalid subscription plan")
        return plan


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ["balance"]


class SubscribeRequestSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()
    plan = serializers.SerializerMethodField(read_only=True)

    def validate(self, data):
        try:
            data["plan"] = SubscriptionPlan.objects.get(id=data["plan_id"])
        except SubscriptionPlan.DoesNotExist:
            raise serializers.ValidationError({"plan_id": "Plan not found."})
        return data


class SubscriptionStatusSerializer(serializers.Serializer):
    plan = SubscriptionPlanSerializer()
    wallet_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    subscribed_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    request_balance = serializers.IntegerField()
