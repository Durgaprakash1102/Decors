from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import License


@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):

    list_display = (
        "company_name",
        "domain",
        "status_badge",
        "issued_on",
        "expires_on",
        "days_remaining",
        "is_active",
        "uploaded_at",
    )

    list_filter = (
        "status",
        "is_active",
    )

    search_fields = (
        "company_name",
        "domain",
    )

    ordering = (
        "-is_active",
        "-uploaded_at",
    )

    date_hierarchy = "uploaded_at"

    readonly_fields = (
        "company_name",
        "domain",
        "issued_on",
        "expires_on",
        "status",
        "is_active",
        "uploaded_at",
        "replaced_at",
        "created_at",
        "updated_at",

        # Email Notification Status
        "seven_day_email_sent",
        "three_day_email_sent",
        "one_day_email_sent",
        "expired_email_sent",
    )

    fieldsets = (
        (
            "License Information",
            {
                "fields": (
                    "company_name",
                    "domain",
                    "issued_on",
                    "expires_on",
                )
            },
        ),

        (
            "License Status",
            {
                "fields": (
                    "status",
                    "is_active",
                    "uploaded_at",
                    "replaced_at",
                )
            },
        ),

        (
            "Email Notification Status",
            {
                "fields": (
                    "seven_day_email_sent",
                    "three_day_email_sent",
                    "one_day_email_sent",
                    "expired_email_sent",
                )
            },
        ),

        (
            "Audit Information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def status_badge(self, obj):

        colors = {
            License.Status.ACTIVE: "#198754",     # Green
            License.Status.EXPIRED: "#dc3545",    # Red
            License.Status.REPLACED: "#6c757d",   # Gray
        }

        color = colors.get(obj.status, "#0d6efd")

        return format_html(
            """
            <span style="
                background:{};
                color:white;
                padding:5px 12px;
                border-radius:15px;
                font-weight:600;
                font-size:12px;
            ">
                {}
            </span>
            """,
            color,
            obj.status,
        )

    status_badge.short_description = "Status"

    def days_remaining(self, obj):

        if obj.status != License.Status.ACTIVE:
            return format_html(
                '<span style="color:#6c757d;font-weight:bold;">-</span>'
            )

        days = (obj.expires_on - timezone.now().date()).days

        if days < 0:
            return format_html(
                '<span style="color:#dc3545;font-weight:bold;">Expired</span>'
            )

        if days <= 3:
            color = "#dc3545"      # Red

        elif days <= 7:
            color = "#fd7e14"      # Orange

        elif days <= 30:
            color = "#ffc107"      # Yellow

        else:
            color = "#198754"      # Green

        return format_html(
            '<span style="color:{};font-weight:bold;">{} Day{}</span>',
            color,
            days,
            "" if days == 1 else "s",
        )

    days_remaining.short_description = "Days Remaining"

    def has_add_permission(self, request):
        """
        Licenses can only be activated
        through the license upload page.
        """
        return False

    def has_delete_permission(self, request, obj=None):
        """
        Never allow deletion of licenses.
        """
        return False

    def has_change_permission(self, request, obj=None):
        """
        Allow viewing the license record.
        All fields are read-only.
        """
        return True

    def save_model(self, request, obj, form, change):
        """
        Prevent manual modifications.
        """
        if change:
            return

        super().save_model(request, obj, form, change)