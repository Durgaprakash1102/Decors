import json
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from .exceptions import (
    DomainMismatchException,
    ExpiredLicenseException,
    InvalidLicenseException,
    NoActiveLicenseException,
)
from .models import License
from .utils import get_current_domain, normalize_domain
from .verifier import verify_signature


class LicenseService:

    @staticmethod
    def get_active_license():
        license_obj = License.objects.filter(is_active=True).first()

        if not license_obj:
            raise NoActiveLicenseException("No active license found.")

        return license_obj

    @staticmethod
    def validate_license(request=None):
        license_obj = LicenseService.get_active_license()

        # Verify RSA signature
        verify_signature(
            license_obj.license_data,
            license_obj.signature,
        )

        # Expiry check
        if timezone.now().date() > license_obj.expires_on:
            license_obj.status = License.Status.EXPIRED
            license_obj.is_active = False
            license_obj.save(update_fields=["status", "is_active"])

            raise ExpiredLicenseException("License has expired.")

        # Domain check
        if request is not None:
            current_domain = get_current_domain(request)
            licensed_domain = normalize_domain(license_obj.domain)

            if current_domain != licensed_domain:
                raise DomainMismatchException(
                    f"License is valid for '{licensed_domain}', "
                    f"but this application is running on '{current_domain}'."
                )

        return license_obj

    @staticmethod
    @transaction.atomic
    def activate_license(uploaded_file, request=None):

        try:
            license_json = json.load(uploaded_file)
        except Exception:
            raise InvalidLicenseException("Invalid license file.")

        payload = license_json.get("payload")
        signature = license_json.get("signature")

        if not payload or not signature:
            raise InvalidLicenseException(
                "License format is invalid."
            )

        # Verify RSA signature
        verify_signature(payload, signature)

        current_domain = get_current_domain(request)
        licensed_domain = normalize_domain(payload["domain"])

        if current_domain != licensed_domain:
            raise DomainMismatchException(
                f"This license is issued for '{licensed_domain}', "
                f"but the application is running on '{current_domain}'."
            )

        issued_on = datetime.strptime(
            payload["issued_on"],
            "%Y-%m-%d",
        ).date()

        expires_on = datetime.strptime(
            payload["expires_on"],
            "%Y-%m-%d",
        ).date()

        if timezone.now().date() > expires_on:
            raise ExpiredLicenseException(
                "License has already expired."
            )

        # Deactivate existing license(s)
        License.objects.filter(
            is_active=True
        ).update(
            is_active=False,
            status=License.Status.REPLACED,
            replaced_at=timezone.now(),
        )

        # Save new license
        license_obj = License.objects.create(
            company_name=payload["company_name"],
            domain=licensed_domain,
            issued_on=issued_on,
            expires_on=expires_on,
            license_data=payload,
            signature=signature,
            status=License.Status.ACTIVE,
            is_active=True,
        )

        return license_obj

    @staticmethod
    def has_active_license():
        return License.objects.filter(
            is_active=True
        ).exists()

    @staticmethod
    def get_license():
        return License.objects.filter(
            is_active=True
        ).first()

    @staticmethod
    def days_remaining():
        license_obj = LicenseService.get_license()

        if not license_obj:
            return 0

        remaining = (
            license_obj.expires_on -
            timezone.now().date()
        ).days

        return max(remaining, 0)