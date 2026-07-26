from django.core.management.base import BaseCommand

from licensing.models import License


class Command(BaseCommand):

    help = "Check current license"

    def handle(self, *args, **kwargs):

        license = License.objects.filter(
            is_active=True
        ).first()

        if not license:

            self.stdout.write(

                self.style.ERROR(

                    "No Active License"

                )

            )

            return

        self.stdout.write(

            f"""
Company : {license.company_name}

Domain : {license.domain}

Issued : {license.issued_on}

Expires : {license.expires_on}

Status : {license.status}
"""
        )