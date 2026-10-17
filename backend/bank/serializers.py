from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import Account, Deposit, Entry


class Credentials(serializers.Serializer):
    email = serializers.EmailField(max_length=150)
    password = serializers.CharField(write_only=True, max_length=128, trim_whitespace=False)


class Registration(Credentials):
    name = serializers.CharField(max_length=100)

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages)
        return value

    def validate_email(self, value):
        value = value.lower()
        if get_user_model().objects.filter(username=value).exists():
            raise serializers.ValidationError('Этот email уже зарегистрирован.')
        return value


class AccountData(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['id', 'slot', 'card_number', 'balance']


class DepositData(serializers.ModelSerializer):
    class Meta:
        model = Deposit
        fields = ['id', 'balance', 'created_at']


class EntryData(serializers.ModelSerializer):
    class Meta:
        model = Entry
        fields = ['id', 'account_id', 'title', 'amount', 'balance_after', 'reference', 'created_at']


class MoneyInput(serializers.Serializer):
    account_id = serializers.IntegerField(min_value=1)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'), max_value=Decimal('1000000.00'))


class HistoryPage(serializers.Serializer):
    results = EntryData(many=True)
    next = serializers.IntegerField(allow_null=True)


class TransferInput(MoneyInput):
    card_number = serializers.RegexField(r'^9900[0-9]{12}$')
    request_id = serializers.UUIDField()


class CloseDepositInput(serializers.Serializer):
    account_id = serializers.IntegerField(min_value=1)
