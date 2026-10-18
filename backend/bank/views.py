from decimal import Decimal
from uuid import uuid4
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiTypes, OpenApiParameter
from .tracing import traced
from .models import Account, Deposit, Entry, Transfer
from .serializers import (Credentials, Registration, AccountData, DepositData,
                          EntryData, MoneyInput, TransferInput, CloseDepositInput, HistoryPage)

User = get_user_model()


@traced('bank.validate')
def validated(serializer, data):
    result = serializer(data=data)
    result.is_valid(raise_exception=True)
    return result.validated_data


def lock_user(user):
    # Serialize account/deposit creation and idempotency checks per user.
    User.objects.select_for_update().get(pk=user.pk)


def lock_account(user, account_id):
    return get_object_or_404(Account.objects.select_for_update(), owner=user, pk=account_id)


@traced('bank.balance_change')
def change(account, amount, title, reference=None):
    new_balance = account.balance + amount
    if new_balance < 0:
        raise ValidationError('Недостаточно средств.')
    if new_balance > Decimal('999999999999.99'):
        raise ValidationError('Превышен максимальный баланс.')
    account.balance = new_balance
    account.save(update_fields=['balance'])
    Entry.objects.create(owner=account.owner, account=account, title=title, amount=amount,
                         balance_after=new_balance, reference=reference or uuid4())


class Health(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        return Response({'status': 'ok', 'test_mode': settings.ENABLE_TEST_TOPUP})


class Register(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=Registration, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        data = validated(Registration, request.data)
        try:
            with transaction.atomic():
                user = User.objects.create_user(username=data['email'], email=data['email'],
                                               password=data['password'], first_name=data['name'])
                token = Token.objects.create(user=user)
        except IntegrityError:
            raise ValidationError('Этот email уже зарегистрирован.')
        return Response({'token': token.key}, status=status.HTTP_201_CREATED)


class Login(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=Credentials, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        data = validated(Credentials, request.data)
        user = authenticate(username=data['email'].lower(), password=data['password'])
        if not user:
            return Response({'detail': 'Неверный email или пароль.'}, status=401)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key})


class Logout(APIView):
    @extend_schema(request=None, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        request.auth.delete()
        return Response({'detail': 'Вы вышли из аккаунта.'})


class Bank(APIView):
    @extend_schema(responses=OpenApiTypes.OBJECT)
    def get(self, request):
        accounts = Account.objects.filter(owner=request.user).order_by('slot')
        deposit = Deposit.objects.filter(owner=request.user, active=True).first()
        return Response({
            'name': request.user.first_name, 'email': request.user.email, 'currency': 'KZT',
            'accounts': AccountData(accounts, many=True).data,
            'deposit': DepositData(deposit).data if deposit else None,
            'test_mode': settings.ENABLE_TEST_TOPUP,
        })


class Accounts(APIView):
    @extend_schema(request=None, responses=AccountData)
    @transaction.atomic
    def post(self, request):
        lock_user(request.user)
        used = set(Account.objects.filter(owner=request.user).values_list('slot', flat=True))
        free = next((slot for slot in (1, 2) if slot not in used), None)
        if free is None:
            raise ValidationError('Можно открыть не более двух счетов.')
        account = Account.objects.create(owner=request.user, slot=free)
        return Response(AccountData(account).data, status=201)


class TopUp(APIView):
    @extend_schema(request=MoneyInput, responses=AccountData)
    @transaction.atomic
    def post(self, request):
        if not settings.ENABLE_TEST_TOPUP:
            raise PermissionDenied('Тестовое пополнение отключено.')
        data = validated(MoneyInput, request.data)
        account = lock_account(request.user, data['account_id'])
        change(account, data['amount'], 'Тестовое пополнение')
        return Response(AccountData(account).data)


class Transfers(APIView):
    @extend_schema(request=TransferInput, responses=OpenApiTypes.OBJECT)
    @traced('bank.transfer')
    @transaction.atomic
    def post(self, request):
        data = validated(TransferInput, request.data)
        lock_user(request.user)
        previous = Transfer.objects.filter(owner=request.user, request_id=data['request_id']).first()
        if previous:
            if (previous.sender_id != data['account_id'] or previous.amount != data['amount']
                    or previous.recipient.card_number != data['card_number']):
                raise ValidationError('request_id уже использован для другого перевода.')
            return Response({'reference': str(previous.reference), 'replayed': True})
        recipient = get_object_or_404(Account, card_number=data['card_number'])
        # Stable lock order prevents opposite-direction transfer deadlocks.
        locked = {a.id: a for a in Account.objects.select_for_update().filter(
            pk__in=[data['account_id'], recipient.id]).order_by('id')}
        sender = locked.get(data['account_id'])
        if not sender or sender.owner_id != request.user.id:
            raise PermissionDenied('Счёт отправителя недоступен.')
        if sender.id == recipient.id:
            raise ValidationError('Нельзя отправить перевод на ту же карту.')
        recipient = locked[recipient.id]
        transfer = Transfer.objects.create(owner=request.user, request_id=data['request_id'],
                                            sender=sender, recipient=recipient, amount=data['amount'])
        change(sender, -data['amount'], 'Перевод на карту • ' + recipient.card_number[-4:], transfer.reference)
        change(recipient, data['amount'], 'Перевод с карты • ' + sender.card_number[-4:], transfer.reference)
        return Response({'reference': str(transfer.reference), 'replayed': False}, status=201)


class Deposits(APIView):
    @extend_schema(request=None, responses=DepositData)
    @transaction.atomic
    def post(self, request):
        lock_user(request.user)
        if Deposit.objects.filter(owner=request.user, active=True).exists():
            raise ValidationError('Можно открыть только один активный депозит.')
        deposit = Deposit.objects.create(owner=request.user)
        return Response(DepositData(deposit).data, status=201)


class DepositTopUp(APIView):
    @extend_schema(request=MoneyInput, responses=DepositData)
    @transaction.atomic
    def post(self, request):
        data = validated(MoneyInput, request.data)
        lock_user(request.user)
        deposit = get_object_or_404(Deposit.objects.select_for_update(), owner=request.user, active=True)
        account = lock_account(request.user, data['account_id'])
        if deposit.balance + data['amount'] > Decimal('999999999999.99'):
            raise ValidationError('Превышен максимальный баланс депозита.')
        change(account, -data['amount'], 'Пополнение депозита')
        deposit.balance += data['amount']
        deposit.save(update_fields=['balance'])
        return Response(DepositData(deposit).data)


class DepositClose(APIView):
    @extend_schema(request=CloseDepositInput, responses=OpenApiTypes.OBJECT)
    @transaction.atomic
    def post(self, request):
        data = validated(CloseDepositInput, request.data)
        lock_user(request.user)
        deposit = get_object_or_404(Deposit.objects.select_for_update(), owner=request.user, active=True)
        account = lock_account(request.user, data['account_id'])
        change(account, deposit.balance, 'Закрытие депозита')
        deposit.balance = 0
        deposit.active = False
        deposit.save(update_fields=['balance', 'active'])
        return Response({'detail': 'Депозит закрыт. Средства возвращены на счёт.'})


class History(APIView):
    @extend_schema(responses=HistoryPage, parameters=[OpenApiParameter('before', int)])
    def get(self, request):
        # Cursor pagination by immutable entry ID.
        before = request.query_params.get('before')
        entries = Entry.objects.filter(owner=request.user)
        if before:
            try:
                before_id = int(before)
                if before_id < 1:
                    raise ValueError
            except ValueError:
                raise ValidationError('Некорректный курсор истории.')
            entries = entries.filter(id__lt=before_id)
        rows = list(entries[:51])
        return Response({'results': EntryData(rows[:50], many=True).data,
                         'next': rows[49].id if len(rows) > 50 else None})
