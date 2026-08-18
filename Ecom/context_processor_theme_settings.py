from .models import ThemeSettings


def theme_settings(request):

    theme = (
        ThemeSettings.objects
        .filter(is_active=True)
        .first()
    )

    if not theme:

        theme = ThemeSettings.get_settings()

    return {
        "theme": theme
    }