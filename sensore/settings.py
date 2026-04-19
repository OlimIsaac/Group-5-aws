import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve_legacy_db_path():
	configured = os.environ.get("SENSORE_LEGACY_DB", "").strip()
	default_path = BASE_DIR / "legacy_core.sqlite3"

	if not configured:
		return default_path

	candidate = Path(configured).expanduser()
	if not candidate.is_absolute():
		candidate = BASE_DIR / candidate

	if candidate.exists() and candidate.is_dir():
		candidate = candidate / "legacy_core.sqlite3"

	try:
		candidate.parent.mkdir(parents=True, exist_ok=True)
	except OSError:
		return default_path

	if not os.access(candidate.parent, os.W_OK):
		return default_path

	return candidate

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "replace-this-in-prod")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = ["*"]

# Application definition
INSTALLED_APPS = [
	"django.contrib.admin",
	"django.contrib.auth",
	"django.contrib.contenttypes",
	"django.contrib.sessions",
	"django.contrib.messages",
	"django.contrib.staticfiles",
	"rest_framework",
	"django_filters",
	"core",
]

MIDDLEWARE = [
	"django.middleware.security.SecurityMiddleware",
	"django.contrib.sessions.middleware.SessionMiddleware",
	"django.middleware.common.CommonMiddleware",
	"django.middleware.csrf.CsrfViewMiddleware",
	"django.contrib.auth.middleware.AuthenticationMiddleware",
	"django.contrib.messages.middleware.MessageMiddleware",
	"django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "sensore.urls"

TEMPLATES = [
	{
		"BACKEND": "django.template.backends.django.DjangoTemplates",
		"DIRS": [BASE_DIR / "templates", BASE_DIR / "core" / "templates"],
		"APP_DIRS": True,
		"OPTIONS": {
			"context_processors": [
				"django.template.context_processors.debug",
				"django.template.context_processors.request",
				"django.contrib.auth.context_processors.auth",
				"django.contrib.messages.context_processors.messages",
			],
		},
	},
]

WSGI_APPLICATION = "sensore.wsgi.application"

# Database
DATABASES = {
	"default": {
		"ENGINE": "django.db.backends.sqlite3",
		"NAME": str(_resolve_legacy_db_path()),
	}
}

# Custom user model
AUTH_USER_MODEL = "core.User"

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "core" / "static"]

# Rest Framework settings
REST_FRAMEWORK = {
	"DEFAULT_AUTHENTICATION_CLASSES": [
		"rest_framework.authentication.SessionAuthentication",
		"rest_framework.authentication.TokenAuthentication",
	],
	"DEFAULT_PERMISSION_CLASSES": [
		"rest_framework.permissions.IsAuthenticated",
	],
}
