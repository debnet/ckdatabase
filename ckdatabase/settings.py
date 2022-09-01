# coding: utf-8
import datetime
import os
from pathlib import Path

from configurations import Configuration, values
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = Path(__file__).resolve().parent.parent
ENVFILE = BASE_DIR / ".env"


class Base(Configuration):
    if ENVFILE.exists():
        DOTENV = ENVFILE

    # SECURITY WARNING: don't run with debug turned on in production!
    DEBUG = values.BooleanValue(False)
    INTERNAL_IPS = ["127.0.0.1"]
    ALLOWED_HOSTS = values.ListValue(["*"])

    # Site
    SITE_ID = values.IntegerValue(1)
    HOSTNAME = values.Value("")

    # SECURITY WARNING: keep the secret key used in production secret!
    SECRET_KEY = values.SecretValue()

    # Application definition
    INSTALLED_APPS = [
        # Default
        "django.contrib.admin",
        "django.contrib.auth",
        "django.contrib.contenttypes",
        "django.contrib.humanize",
        "django.contrib.sessions",
        "django.contrib.messages",
        "django.contrib.staticfiles",
        # Requirements
        "corsheaders",
        "rest_framework",
        "rest_framework.authtoken",
        "rest_framework_simplejwt",
        "rest_framework_simplejwt.token_blacklist",
        "common",
        "drf_spectacular",
        "drf_spectacular_sidecar",
        # Applications
        "database",
    ]

    # Middleware
    MIDDLEWARE = [
        # CORS Headers
        "corsheaders.middleware.CorsMiddleware",
        # Default
        "django.middleware.security.SecurityMiddleware",
        "django.contrib.sessions.middleware.SessionMiddleware",
        "django.middleware.locale.LocaleMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
        # Application defined
        "common.middleware.ServiceUsageMiddleware",
    ]

    # Database
    DATABASES = values.DatabaseURLValue("sqlite://./db.sqlite3")
    DATABASE_ROUTERS = values.ListValue(("common.router.DatabaseOverrideRouter",))
    DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

    # URL router
    ROOT_URLCONF = "ckdatabase.urls"
    # WSGI entrypoint
    WSGI_APPLICATION = "ckdatabase.wsgi.application"

    # Templates configuration
    TEMPLATES = [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": ("templates",),
            "APP_DIRS": True,
            "OPTIONS": {
                "context_processors": [
                    "django.contrib.auth.context_processors.auth",
                    "django.contrib.messages.context_processors.messages",
                    "django.template.context_processors.request",
                    "django.template.context_processors.media",
                    "django.template.context_processors.debug",
                ],
            },
        },
    ]

    # Authentication backends
    AUTHENTICATION_BACKENDS = ("django.contrib.auth.backends.ModelBackend",)

    # Password validation
    AUTH_PASSWORD_VALIDATORS = [
        {
            "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
        },
        {
            "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        },
        {
            "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
        },
        {
            "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
        },
    ]

    # Internationalization
    LANGUAGE_CODE = values.Value("en")
    TIME_ZONE = values.Value("UTC")
    USE_I18N = values.BooleanValue(True)
    USE_L10N = values.BooleanValue(True)
    USE_TZ = values.BooleanValue(True)

    LANGUAGES = (
        ("fr", _("Français")),
        ("en", _("English")),
    )

    LOCALE_PATHS = (BASE_DIR / "locale",)

    # Static files (CSS, JavaScript, Images)
    STATIC_URL = values.Value("/static/")
    STATIC_ROOT = values.Value(BASE_DIR / "static")

    STATICFILES_DIRS = (BASE_DIR / "statics",)
    STATICFILES_FINDERS = (
        "django.contrib.staticfiles.finders.AppDirectoriesFinder",
        "django.contrib.staticfiles.finders.FileSystemFinder",
    )

    # Media url and directory
    MEDIA_NAME = "medias"
    MEDIA_URL = values.Value("/medias/")
    MEDIA_ROOT = values.Value(os.path.join(BASE_DIR, MEDIA_NAME))

    # Custom settings
    APPEND_SLASH = values.BooleanValue(True)
    CELERY_ENABLE = values.BooleanValue(False)
    CORS_ORIGIN_ALLOW_ALL = values.BooleanValue(False)
    CORS_ALLOW_CREDENTIALS = values.BooleanValue(True)
    CORS_ORIGIN_WHITELIST = values.ListValue(
        [
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ]
    )

    # Django REST Framework configuration
    REST_FRAMEWORK = {
        "DEFAULT_PERMISSION_CLASSES": ("database.permissions.AccessApiPermissions",),
        "DEFAULT_AUTHENTICATION_CLASSES": (
            "rest_framework.authentication.TokenAuthentication",
            "rest_framework.authentication.SessionAuthentication",
            "rest_framework_simplejwt.authentication.JWTAuthentication",
        ),
        "DEFAULT_RENDERER_CLASSES": (
            "rest_framework.renderers.JSONRenderer",
            "rest_framework.renderers.BrowsableAPIRenderer",
            "rest_framework.renderers.AdminRenderer",
        ),
        "DEFAULT_PARSER_CLASSES": (
            "rest_framework.parsers.JSONParser",
            "rest_framework.parsers.FormParser",
            "rest_framework.parsers.MultiPartParser",
            "rest_framework.parsers.FileUploadParser",
        ),
        "DEFAULT_PAGINATION_CLASS": "common.api.pagination.CustomPageNumberPagination",
        "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
        "PAGE_SIZE": 10,
        "TEST_REQUEST_DEFAULT_FORMAT": "json",
        "COERCE_DECIMAL_TO_STRING": True,
        "HYPERLINKED": True,
    }

    SPECTACULAR_SETTINGS = {
        "TITLE": "Crusader Kings Database API",
        "DESCRIPTION": "",
        "VERSION": "1",
        "SERVE_PUBLIC": False,
        "SERVE_INCLUDE_SCHEMA": True,
        "SERVE_PERMISSIONS": ("database.permissions.AccessApiPermissions",),
        "SWAGGER_UI_DIST": "SIDECAR",
        "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
        "REDOC_DIST": "SIDECAR",
    }

    # JSON Web Token Authentication
    SIMPLE_JWT = {
        "ACCESS_TOKEN_LIFETIME": datetime.timedelta(minutes=5),
        "REFRESH_TOKEN_LIFETIME": datetime.timedelta(days=1),
        "ROTATE_REFRESH_TOKENS": False,
        "BLACKLIST_AFTER_ROTATION": True,
        "ALGORITHM": "HS256",
        "SIGNING_KEY": values.SecretValue(environ_name="SECRET_KEY"),
        "VERIFYING_KEY": None,
        "AUTH_HEADER_TYPES": (
            "Bearer",
            "JWT",
        ),
        "USER_ID_FIELD": "id",
        "USER_ID_CLAIM": "user_id",
        "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
        "TOKEN_TYPE_CLAIM": "token_type",
        "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
        "SLIDING_TOKEN_LIFETIME": datetime.timedelta(minutes=5),
        "SLIDING_TOKEN_REFRESH_LIFETIME": datetime.timedelta(days=1),
    }

    # Login URLs
    LOGIN_URL = values.Value("login")
    LOGOUT_URL = values.Value("logout")
    LOGIN_REDIRECT_URL = values.Value("admin:index")
    LOGOUT_REDIRECT_URL = values.Value("admin:index")

    # User substitution
    AUTH_USER_MODEL = "database.User"

    # Durée de validité du lien de réinitialisation de mot de passe
    PASSWORD_RESET_TIMEOUT_DAYS = values.IntegerValue(1)

    # Gestionnaire utilisé pour l'import des fichiers
    FILE_UPLOAD_HANDLERS = ("common.utils.TemporaryFileHandler",)

    # Taille du payload maximum autorisée et permissions à l'upload
    DATA_UPLOAD_MAX_MEMORY_SIZE = values.IntegerValue(10485760)
    FILE_UPLOAD_PERMISSIONS = values.IntegerValue(0o644)

    # Stocke le token CSRF en session plutôt que dans un cookie
    CSRF_USE_SESSIONS = values.BooleanValue(False)

    # E-mail configuration
    EMAIL_HOST = values.Value("")
    EMAIL_HOST_USER = values.Value("")
    EMAIL_HOST_PASSWORD = values.Value("")
    EMAIL_PORT = values.IntegerValue(25)
    EMAIL_SUBJECT_PREFIX = values.Value("")
    EMAIL_USE_TLS = values.BooleanValue(False)
    EMAIL_USE_SSL = values.BooleanValue(False)
    EMAIL_TIMEOUT = values.IntegerValue(300)
    DEFAULT_FROM_EMAIL = values.Value("Admin <admin@debnet.fr>")

    # Logging configuration
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "simple": {
                "format": "[%(asctime)s] %(levelname)7s: %(message)s",
                "datefmt": "%d/%m/%Y %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "level": "INFO",
                "class": "logging.StreamHandler",
                "formatter": "simple",
            },
            "file": {
                "level": "WARNING",
                "class": "logging.FileHandler",
                "filename": "database.log",
                "formatter": "simple",
            },
        },
        "loggers": {
            "": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": True,
            },
            "django": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
        },
    }

    # Common
    IGNORE_LOG = values.BooleanValue(False)
    IGNORE_LOG_NO_USER = values.BooleanValue(False)
    IGNORE_LOG_ENTITY_FIELDS = values.BooleanValue(True)
    IGNORE_GLOBAL = values.BooleanValue(False)
    SERVICE_USAGE = values.BooleanValue(True)


class Prod(Base):
    """
    Configuration de production
    """

    DEBUG = False

    # HTTPS/SSL
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = values.BooleanValue(True)
    SESSION_COOKIE_SECURE = values.BooleanValue(True)
    CSRF_COOKIE_SECURE = values.BooleanValue(True)

    DJANGO_REDIS_IGNORE_EXCEPTIONS = True
    SESSION_ENGINE = "django.contrib.sessions.backends.cache"
    SESSION_CACHE_ALIAS = "default"

    CACHE_MIDDLEWARE_ALIAS = "default"
    CACHE_MIDDLEWARE_SECONDS = 0
    CACHE_MIDDLEWARE_KEY_PREFIX = ""

    # Cache
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": [
                values.Value("127.0.0.1:6379:1", environ_name="REDIS_CACHE"),
            ],
            "KEY_PREFIX": "cache",
            "TIMEOUT": 3600,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "IGNORE_EXCEPTIONS": True,
            },
        }
    }

    # Cache middleware
    MIDDLEWARE = [
        "django.middleware.cache.UpdateCacheMiddleware",
        *Base.MIDDLEWARE,
        "django.middleware.cache.FetchFromCacheMiddleware",
    ]

    # Celery configuration
    CELERY_ENABLE = values.BooleanValue(True)
    CELERY_BROKER_URL = BROKER_URL = values.Value("redis://localhost:6379/1", environ_name="CELERY_BROKER_URL")
    CELERY_BROKER_TRANSPORT_OPTIONS = BROKER_TRANSPORT_OPTIONS = {
        "visibility_timeout": 3600,
        "fanout_prefix": True,
        "fanout_patterns": True,
    }
    CELERY_ACCEPT_CONTENT = ["json", "msgpack", "yaml", "pickle"]
    CELERY_RESULT_SERIALIZER = "pickle"
    CELERY_RESULT_BACKEND = values.Value("redis")
    CELERY_TASK_SERIALIZER = "pickle"
    CELERY_TASK_RESULT_EXPIRES = 3600
    CELERY_DISABLE_RATE_LIMITS = True
    CELERY_TASK_ALWAYS_EAGER = values.BooleanValue(False, environ_name="CELERY_TASK_ALWAYS_EAGER")
    CELERY_TASK_EAGER_PROPAGATES = False
    CELERY_TASK_DEFAULT_QUEUE = values.Value("celery", environ_name="QUEUE_NAME")


class Test(Base):
    """
    Configuration de développement
    """

    DEBUG = True
    INTERNAL_IPS = ["localhost", "127.0.0.1", "[::1]", "testserver", "*"]
    ALLOWED_HOSTS = INTERNAL_IPS

    # Celery configuration
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_RESULT_BACKEND = "cache"
    CELERY_CACHE_BACKEND = "memory"

    # Django Debug Toolbar
    DEBUG_TOOLBAR_ENABLE = True
    if DEBUG_TOOLBAR_ENABLE:
        INSTALLED_APPS = Base.INSTALLED_APPS + ["debug_toolbar"]
        MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + Base.MIDDLEWARE
        DEBUG_TOOLBAR_PATCH_SETTINGS = False
        DEBUG_TOOLBAR_CONFIG = {
            "JQUERY_URL": "",
        }

    # Disable password security
    AUTH_PASSWORD_VALIDATORS = []

    # Cache
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "unique-snowflake",
            "TIMEOUT": 3600,
        },
    }
