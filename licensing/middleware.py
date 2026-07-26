from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

from .exceptions import (
    DomainMismatchException,
    ExpiredLicenseException,
    InvalidSignatureException,
    NoActiveLicenseException,
)
from .services import LicenseService


class LicenseMiddleware(MiddlewareMixin):
    """
    Protects the application by ensuring a valid license
    exists before allowing access.
    """

    EXCLUDED_PATHS = (
        "/license/",
        "/admin/",
        "/static/",
        "/media/",
        "/favicon.ico",
    )

    def process_request(self, request):

        path = request.path

        # Allow excluded URLs
        if any(path.startswith(p) for p in self.EXCLUDED_PATHS):
            return None

        try:
            LicenseService.validate_license(request)
            return None

        except NoActiveLicenseException:
            return redirect(reverse("licensing:activate"))

        except InvalidSignatureException:
            return redirect(reverse("licensing:activate"))

        except DomainMismatchException:
            return redirect(reverse("licensing:activate"))

        except ExpiredLicenseException:
            return redirect(reverse("licensing:expired"))