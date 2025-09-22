from rest_framework import serializers
from payment.models import Transaction

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = "__all__"

class PaystackWithdrawSerializer(serializers.Serializer):
    account_number = serializers.CharField(required=True)
    bank_code = serializers.CharField(required=True)
    amount = serializers.DecimalField(required=True, max_digits=10, decimal_places=2)

    