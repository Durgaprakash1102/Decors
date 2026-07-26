from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from licensing.models import License


User = get_user_model()


class Command(BaseCommand):
    help = "Send license expiry reminder emails."

    def handle(self, *args, **options):

        license_obj = License.objects.filter(
            is_active=True
        ).first()

        if not license_obj:
            self.stdout.write(
                self.style.WARNING("No active license found.")
            )
            return

        emails = list(
            User.objects.filter(
                is_superuser=True,
                is_active=True,
            )
            .exclude(email="")
            .values_list("email", flat=True)
        )

        if not emails:
            self.stdout.write(
                self.style.WARNING("No superuser email addresses found.")
            )
            return

        days_remaining = (
            license_obj.expires_on - timezone.now().date()
        ).days

        subject = None
        message = None
        update_field = None

        # -----------------------------
        # 7 Days Remaining
        # -----------------------------
        if (
            days_remaining == 7
            and not license_obj.seven_day_email_sent
        ):
            subject = "License Expiry Reminder - 7 Days Remaining"

            message = f"""
Dear Administrator,

This is a reminder that your application's license will expire in 7 days.

License Details
----------------------------
Company      : {license_obj.company_name}
Domain       : {license_obj.domain}
Expiry Date  : {license_obj.expires_on}

To ensure uninterrupted access to the application, please renew your license before the expiry date.

Please contact the application owner to obtain a new license file and upload it through the License Management page.

Failure to renew the license before the expiry date may result in restricted access to the application.

Regards,
License Management System
""".strip()

            update_field = "seven_day_email_sent"

        # -----------------------------
        # 3 Days Remaining
        # -----------------------------
        elif (
            days_remaining == 3
            and not license_obj.three_day_email_sent
        ):
            subject = "URGENT: License Expires in 3 Days"

            message = f"""
Dear Administrator,

Your application's license will expire in 3 days.

License Details
----------------------------
Company      : {license_obj.company_name}
Domain       : {license_obj.domain}
Expiry Date  : {license_obj.expires_on}

Please contact the application owner immediately to obtain a renewed license file.

Upload the new license before the expiry date to avoid interruption of service.

Regards,
License Management System
""".strip()

            update_field = "three_day_email_sent"

        # -----------------------------
        # 1 Day Remaining
        # -----------------------------
        elif (
            days_remaining == 1
            and not license_obj.one_day_email_sent
        ):
            subject = "FINAL REMINDER: License Expires Tomorrow"

            message = f"""
Dear Administrator,

This is the final reminder that your application's license will expire tomorrow.

License Details
----------------------------
Company      : {license_obj.company_name}
Domain       : {license_obj.domain}
Expiry Date  : {license_obj.expires_on}

Please contact the application owner immediately to obtain a new license file.

Upload the renewed license before the expiry date to prevent disruption of the application.

Regards,
License Management System
""".strip()

            update_field = "one_day_email_sent"

        # -----------------------------
        # Expired
        # -----------------------------
        elif (
            days_remaining < 0
            and not license_obj.expired_email_sent
        ):
            subject = "License Expired"

            message = f"""
Dear Administrator,

Your application's license has expired.

License Details
----------------------------
Company      : {license_obj.company_name}
Domain       : {license_obj.domain}
Expiry Date  : {license_obj.expires_on}

The application license is no longer valid.

Please contact the application owner to obtain a renewed license file.

Once you receive the new license, upload it through the License Management page to restore normal operation of the application.

Regards,
License Management System
""".strip()

            update_field = "expired_email_sent"

        # -----------------------------
        # Send Email
        # -----------------------------
        if subject:

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=emails,
                fail_silently=False,
            )

            setattr(license_obj, update_field, True)
            license_obj.save(update_fields=[update_field])

            self.stdout.write(
                self.style.SUCCESS(
                    f"License notification sent successfully to {len(emails)} administrator(s)."
                )
            )

        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "No license notification needs to be sent today."
                )
            )