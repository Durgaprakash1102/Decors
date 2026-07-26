from django import forms


class LicenseUploadForm(forms.Form):
    license_file = forms.FileField(
        label="License File"
    )

    def clean_license_file(self):
        file = self.cleaned_data["license_file"]

        allowed_extensions = (".lic", ".json")

        if not file.name.lower().endswith(allowed_extensions):
            raise forms.ValidationError(
                "Only .lic or .json files are allowed."
            )

        return file