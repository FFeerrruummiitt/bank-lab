from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import override_settings, TransactionTestCase
from rest_framework.test import APIClient, APITestCase
from .models import Account, Deposit, Entry, Transfer

User = get_user_model()


@override_settings(ENABLE_TEST_TOPUP=True, REST_FRAMEWORK={
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.TokenAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
})
class BankTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice@example.com', password='Lab-password-478!')
        self.other = User.objects.create_user(username='bob@example.com', password='Lab-password-478!')
        self.client.force_authenticate(self.user)
        self.a = Account.objects.create(owner=self.user, slot=1, balance=1000)
        self.b = Account.objects.create(owner=self.other, slot=1, balance=100)

    def post(self, path, data=None):
        return self.client.post('/api/' + path + '/', data or {}, format='json')

    def transfer(self, **kwargs):
        return dict(account_id=self.a.id, card_number=self.b.card_number,
                    amount='100.25', request_id=str(uuid4()), **kwargs)

    def test_auth_registration_login_logout(self):
        self.client = APIClient()
        self.assertEqual(self.client.get('/api/bank/').status_code, 401)
        data = {'email': 'New@Example.com', 'name': 'Новый', 'password': 'Lab-password-478!'}
        result = self.post('auth/register', data)
        self.assertEqual(result.status_code, 201, result.data)
        self.assertNotIn('password', result.data)
        self.assertEqual(self.post('auth/register', data).status_code, 400)
        self.assertEqual(self.post('auth/login', {'email': data['email'], 'password': 'wrong'}).status_code, 401)
        token = self.post('auth/login', data).data['token']
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token)
        self.assertEqual(self.client.get('/api/bank/').status_code, 200)
        self.assertEqual(self.post('auth/logout').status_code, 200)
        self.assertEqual(self.client.get('/api/bank/').status_code, 401)

    def test_weak_password_is_validation_error(self):
        self.client = APIClient()
        response = self.post('auth/register', {'email': 'weak@example.com', 'name': 'Тест', 'password': '123'})
        self.assertEqual(response.status_code, 400)

    def test_swagger_and_schema_are_accessible(self):
        public = APIClient()
        self.assertEqual(public.get('/api/docs/').status_code, 200)
        self.assertEqual(public.get('/api/schema/').status_code, 200)

    def test_two_account_limit(self):
        self.assertEqual(self.post('accounts').status_code, 201)
        self.assertEqual(self.post('accounts').status_code, 400)
        self.assertEqual(Account.objects.filter(owner=self.user).count(), 2)

    def test_foreign_account_and_history_are_private(self):
        result = self.post('topup', {'account_id': self.b.id, 'amount': '100'})
        self.assertEqual(result.status_code, 404)
        Entry.objects.create(owner=self.other, account=self.b, title='Private', amount=1, balance_after=101)
        self.assertEqual(self.client.get('/api/history/').data['results'], [])
        self.assertEqual(len(self.client.get('/api/bank/').data['accounts']), 1)

    def test_invalid_money(self):
        for amount in ['0', '-1', '0.001', 'NaN', 'Infinity', '1000000.01', '1e999', None]:
            self.assertEqual(self.post('topup', {'account_id': self.a.id, 'amount': amount}).status_code, 400, amount)
        self.a.refresh_from_db()
        self.assertEqual(self.a.balance, 1000)

    @override_settings(ENABLE_TEST_TOPUP=False)
    def test_test_faucet_can_be_disabled(self):
        self.assertEqual(self.post('topup', {'account_id': self.a.id, 'amount': '10'}).status_code, 403)

    def test_transfer_exact_balances_and_retry(self):
        data = self.transfer()
        first = self.post('transfers', data)
        self.assertEqual(first.status_code, 201, first.data)
        second = self.post('transfers', data)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['reference'], second.data['reference'])
        self.a.refresh_from_db(); self.b.refresh_from_db()
        self.assertEqual(self.a.balance, Decimal('899.75'))
        self.assertEqual(self.b.balance, Decimal('200.25'))
        self.assertEqual(Entry.objects.count(), 2)
        data['amount'] = '1'
        self.assertEqual(self.post('transfers', data).status_code, 400)

    def test_failed_transfer_rolls_back_everything(self):
        data = self.transfer(); data['amount'] = '1001'
        self.assertEqual(self.post('transfers', data).status_code, 400)
        self.a.refresh_from_db(); self.b.refresh_from_db()
        self.assertEqual((self.a.balance, self.b.balance), (1000, 100))
        self.assertFalse(Transfer.objects.exists())
        self.assertFalse(Entry.objects.exists())

    def test_self_unknown_and_foreign_sender_rejected(self):
        data = self.transfer(); data['card_number'] = self.a.card_number
        self.assertEqual(self.post('transfers', data).status_code, 400)
        data['card_number'] = '9900000000000000'
        self.assertEqual(self.post('transfers', data).status_code, 404)
        data['account_id'] = self.b.id; data['card_number'] = self.a.card_number
        self.assertEqual(self.post('transfers', data).status_code, 403)

    def test_deposit_lifecycle_and_insufficient_funds(self):
        self.assertEqual(self.post('deposits').status_code, 201)
        self.assertEqual(self.post('deposits').status_code, 400)
        self.assertEqual(self.post('deposits/topup', {'account_id': self.a.id, 'amount': '2000'}).status_code, 400)
        self.assertEqual(Deposit.objects.get(owner=self.user).balance, 0)
        self.assertEqual(self.post('deposits/topup', {'account_id': self.a.id, 'amount': '125.50'}).status_code, 200)
        self.a.refresh_from_db(); self.assertEqual(self.a.balance, Decimal('874.50'))
        self.assertEqual(self.post('deposits/close', {'account_id': self.b.id}).status_code, 404)
        self.assertEqual(self.post('deposits/close', {'account_id': self.a.id}).status_code, 200)
        self.a.refresh_from_db(); self.assertEqual(self.a.balance, 1000)
        self.assertEqual(self.post('deposits/close', {'account_id': self.a.id}).status_code, 404)
        self.assertEqual(self.post('deposits').status_code, 201)

    def test_history_pagination(self):
        Entry.objects.bulk_create([Entry(owner=self.user, account=self.a, title='Test', amount=1, balance_after=1000) for _ in range(55)])
        page = self.client.get('/api/history/').data
        self.assertEqual(len(page['results']), 50)
        second = self.client.get('/api/history/', {'before': page['next']}).data
        self.assertEqual(len(second['results']), 5)
        self.assertIsNone(second['next'])
        self.assertEqual(self.client.get('/api/history/?before=bad').status_code, 400)


class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='parallel@example.com')

    def call(self, path, data):
        close_old_connections()
        try:
            client = APIClient(); client.force_authenticate(User.objects.get(pk=self.user.pk))
            return client.post(path, data, format='json').status_code
        finally:
            close_old_connections()

    def test_concurrent_account_creation_stays_within_limit(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            codes = list(pool.map(lambda _: self.call('/api/accounts/', {}), range(4)))
        self.assertEqual(sorted(codes), [201, 201, 400, 400])
        self.assertEqual(Account.objects.filter(owner=self.user).count(), 2)

    def test_concurrent_transfer_retries_only_charge_once(self):
        sender = Account.objects.create(owner=self.user, slot=1, balance=1000)
        recipient = Account.objects.create(owner=self.user, slot=2)
        data = {'account_id': sender.id, 'card_number': recipient.card_number, 'amount': '150.25', 'request_id': str(uuid4())}
        with ThreadPoolExecutor(max_workers=3) as pool:
            codes = list(pool.map(lambda _: self.call('/api/transfers/', data), range(3)))
        self.assertEqual(sorted(codes), [200, 200, 201])
        sender.refresh_from_db(); recipient.refresh_from_db()
        self.assertEqual(sender.balance, Decimal('849.75'))
        self.assertEqual(recipient.balance, Decimal('150.25'))
        self.assertEqual(Transfer.objects.count(), 1)
