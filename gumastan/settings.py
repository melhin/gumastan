import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Path to the ONNX model directory (genai_config.json + tokenizer files).
EVENT_MODEL_PATH = Path(os.environ.get("EVENT_MODEL_PATH", BASE_DIR / "models"))

SECRET_KEY = "change-me-in-production"

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_prodserver",
    "django_tasks_db",
    "core",
]

TASKS = {
    "default": {
        "BACKEND": "django_tasks_db.backend.DatabaseBackend",
    },
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

ROOT_URLCONF = "gumastan.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

PRODUCTION_PROCESSES = {
            "web-with-command-workers": {
                "BACKEND": "django_melnottam.prodserver_backends.process.ProcessWorkerServer",
                "ARGS": {
                    "workers": 2,
                    "bind": "0.0.0.0:8000",
                    "app_path": "gumastan.asgi:application",
                    "django_settings_module": "myapp.settings",
                    "command_workers": [
                        {
                            "command": "db_worker",
                            "options": {"reload": False},
                            "instances":1,
                        },
                    ],
                },
            },
        }

WSGI_APPLICATION = "gumastan.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Max body size for uploaded images (bytes).
MAX_BODY_BYTES = 20 * 1024 * 1024

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
