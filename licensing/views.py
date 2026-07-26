from django.contrib import messages
from django.shortcuts import redirect, render

from .exceptions import (
    DomainMismatchException,
    ExpiredLicenseException,
    InvalidLicenseException,
    InvalidSignatureException,
)

from .forms import LicenseUploadForm
from .services import LicenseService


def activate_license(request):

    if request.method == "POST":

        form = LicenseUploadForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():

            try:

                LicenseService.activate_license(
                    form.cleaned_data["license_file"],
                    request
                )

                messages.success(
                    request,
                    "License activated successfully."
                )

                return redirect("/")

            except InvalidLicenseException as e:

                messages.error(request, str(e))

            except InvalidSignatureException as e:

                messages.error(request, str(e))

            except DomainMismatchException as e:

                messages.error(request, str(e))

            except ExpiredLicenseException as e:

                messages.error(request, str(e))

    else:

        form = LicenseUploadForm()

    return render(
        request,
        "licensing/activate.html",
        {
            "form": form
        }
    )

def expired_license(request):

    form = LicenseUploadForm()

    if request.method == "POST":

        form = LicenseUploadForm(
            request.POST,
            request.FILES
        )

        if form.is_valid():

            try:

                LicenseService.activate_license(
                    form.cleaned_data["license_file"],
                    request
                )

                messages.success(
                    request,
                    "License renewed successfully."
                )

                return redirect("/")

            except Exception as e:

                messages.error(request, str(e))

    return render(

        request,

        "licensing/expired.html",

        {
            "form": form
        }

    )