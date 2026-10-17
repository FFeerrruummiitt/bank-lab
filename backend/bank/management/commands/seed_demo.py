from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from bank.models import Account, Deposit
from bank.views import change


class Command(BaseCommand):
    help = 'Create fictional demo users once; never reset existing users or balances.'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        User = get_user_model()
        for email, name, cards in [
            ('alice@banklab.test', 'Алия', [('9900000000000001', '100000'), ('9900000000000002', '25000')]),
            ('bob@banklab.test', 'Данияр', [('9900000000000003', '10000')]),
        ]:
            if User.objects.filter(username=email).exists():
                continue
            user = User.objects.create_user(username=email, email=email, first_name=name, password='Lab-demo-478!')
            for slot, (card, balance) in enumerate(cards, 1):
                account = Account.objects.create(owner=user, slot=slot, card_number=card)
                change(account, Decimal(balance), 'Стартовое тестовое пополнение')
            if email == 'alice@banklab.test':
                deposit = Deposit.objects.create(owner=user, balance=Decimal('5000'))
                account = Account.objects.get(owner=user, slot=1)
                change(account, -deposit.balance, 'Пополнение депозита')
        self.stdout.write(self.style.SUCCESS('Demo data ready. Existing users were preserved.'))
