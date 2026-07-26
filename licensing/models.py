from django.db import models
from django.utils import timezone


class License(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        REPLACED = "REPLACED", "Replaced"
        EXPIRED = "EXPIRED", "Expired"

    company_name = models.CharField(max_length=255)

    domain = models.CharField(max_length=255)

    issued_on = models.DateField()

    expires_on = models.DateField()

    license_data = models.JSONField()

    signature = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )

    is_active = models.BooleanField(default=True)

    uploaded_at = models.DateTimeField(auto_now_add=True)

    replaced_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)
    seven_day_email_sent = models.BooleanField(default=False)
    three_day_email_sent = models.BooleanField(default=False)
    one_day_email_sent = models.BooleanField(default=False)
    expired_email_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.company_name} ({self.expires_on})"

    @property
    def is_expired(self):
        return timezone.now().date() > self.expires_on

    @property
    def days_remaining(self):
        return (self.expires_on - timezone.now().date()).days