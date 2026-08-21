from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


from dotenv import load_dotenv

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECRET_KEY = os.getenv(
#     "DJANGO_SECRET_KEY",
#     ""
# )
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-5$6z69*l21(4l@ct61zp&l_n2rn7%@f4-+4tho10hu_s2tgdue"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv(
    "DJANGO_DEBUG",
    "False"
).lower() == "true"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "DJANGO_ALLOWED_HOSTS",
        "127.0.0.1,localhost"
    ).split(",")
    if host.strip()
]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "Ecom",
    "offline_sales",
     'sslserver',
     "licensing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "licensing.middleware.LicenseMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'Ecom.middleware.CleanupMiddleware',
]

ROOT_URLCONF = "Decors.urls"
AUTH_USER_MODEL = 'Ecom.User'

import os
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                'Ecom.context_processors.header_categories',
                'Ecom.admin_context.low_stock_context',
                "Ecom.context_processor.base_template",
                'Ecom.custom_context.get_nav_counts',
                'Ecom.context_processors_site_settings.site_settings',
                'Ecom.context_processor_theme_settings.theme_settings',
            ],
        },
    },
]

WSGI_APPLICATION = "Decors.wsgi.application"


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}
# DATABASES = {
#     "default": {
#         "ENGINE": os.getenv(
#             "DB_ENGINE",
#             "django.db.backends.sqlite3"
#         ),

#         "NAME": os.getenv(
#             "DB_NAME",
#             BASE_DIR / "db.sqlite3"
#         ),

#         "USER": os.getenv(
#             "DB_USER",
#             ""
#         ),

#         "PASSWORD": os.getenv(
#             "DB_PASSWORD",
#             ""
#         ),

#         "HOST": os.getenv(
#             "DB_HOST",
#             ""
#         ),

#         "PORT": os.getenv(
#             "DB_PORT",
#             ""
#         ),
#     }
# }

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",},
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

RAZORPAY_KEY_ID = os.getenv(
    "RAZORPAY_KEY_ID",
    ""
)

RAZORPAY_KEY_SECRET = os.getenv(
    "RAZORPAY_KEY_SECRET",
    ""
)

RAZORPAY_CURRENCY = os.getenv(
    "RAZORPAY_CURRENCY",
    "INR"
)


EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend"
)

EMAIL_HOST = os.getenv(
    "EMAIL_HOST",
    "smtp.gmail.com"
)

EMAIL_PORT = int(
    os.getenv(
        "EMAIL_PORT",
        "587"
    )
)

EMAIL_USE_TLS = (
    os.getenv(
        "EMAIL_USE_TLS",
        "True"
    ).lower() == "true"
)

EMAIL_HOST_USER = os.getenv(
    "EMAIL_HOST_USER",
    ""
)

EMAIL_HOST_PASSWORD = os.getenv(
    "EMAIL_HOST_PASSWORD",
    ""
)

DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL",
    EMAIL_HOST_USER
)

SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# ========== LOGIN URL ==========
LOGIN_URL = 'Ecom:login'
LOGIN_REDIRECT_URL = 'Ecom:home'
LOGOUT_REDIRECT_URL = 'Ecom:home'

SECURE_SSL_REDIRECT = False  # Set to False for development
SESSION_COOKIE_SECURE = False  # Set to False for development
CSRF_COOKIE_SECURE = False  # Set to False for development
SECURE_HSTS_SECONDS = 0  # Disable HSTS for development

if DEBUG:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "handlers": {
        "license_file": {
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "license.log",
            "level": "INFO",
        },
    },

    "loggers": {
        "licensing": {
            "handlers": ["license_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

TWO_FACTOR_API_KEY = os.getenv(
    "TWO_FACTOR_API_KEY",
    ""
)
ADMIN_SECRET_KEY = os.getenv(
    "ADMIN_SECRET_KEY",
    ""
)

SMS_ENABLED = (
    os.getenv(
        "SMS_ENABLED",
        "True"
    ).lower() == "true"
)