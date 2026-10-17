import secrets
import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


def card_number():
    # Fictional numbers for this isolated lab, never real payment cards.
    return '9900' + ''.join(str(secrets.randbelow(10)) for _ in range(12))


class Account(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    slot = models.PositiveSmallIntegerField()
    card_number = models.CharField(max_length=16, unique=True, default=card_number)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'slot'], name='unique_owner_slot'),
            models.CheckConstraint(condition=Q(slot__in=[1, 2]), name='two_account_slots'),
            models.CheckConstraint(condition=Q(balance__gte=0), name='positive_account_balance'),
        ]


class Deposit(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner'], condition=Q(active=True), name='one_active_deposit'),
            models.CheckConstraint(condition=Q(balance__gte=0), name='positive_deposit_balance'),
        ]


class Transfer(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    request_id = models.UUIDField()
    sender = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='sent')
    recipient = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='received')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.UUIDField(default=uuid.uuid4, unique=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['owner', 'request_id'], name='unique_transfer_request')]


class Entry(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    title = models.CharField(max_length=100)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    balance_after = models.DecimalField(max_digits=14, decimal_places=2)
    reference = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-id']
