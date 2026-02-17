import os


def setup():
    try:
        from django_cmd import configure

        configure()
    except ImportError:
        pass

    if "DJANGO_SETTINGS_MODULE" not in os.environ:
        return

    import django

    django.setup()
