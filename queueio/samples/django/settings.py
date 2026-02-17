DEBUG = True

SECRET_KEY = "insecure-example-key"

INSTALLED_APPS = [
    "queueio.django",
    "queueio.samples.django",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ROOT_URLCONF = "queueio.samples.django.urls"
