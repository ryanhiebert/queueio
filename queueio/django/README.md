# Django Integration

## Settings

When running `queueio run`,
Django isn't started automatically.
If your routines use the Django ORM or other Django features,
queueio needs to call `django.setup()` before importing routine modules.

The `queueio[django]` extra includes
[django-cmd](https://pypi.org/project/django-cmd/),
which reads `tool.django.settings` from `pyproject.toml`
and sets `DJANGO_SETTINGS_MODULE` automatically:

```toml
[tool.django]
settings = "myproject.settings"
```

If `DJANGO_SETTINGS_MODULE` is set in the environment
(whether by `django-cmd` or directly),
queueio calls `django.setup()` before registering routines.

## Runserver

!!! warning "Development server only"

    The runserver integration only affects the `runserver` management command.
    Production servers like gunicorn need their own lifecycle hooks.

queueio ships a Django app
that overrides the `runserver` management command
to wrap the server in `with activate():`,
giving you automatic lifecycle management
of the broker connection and background threads
during development.

### Setup

If you use [djp](https://djp.readthedocs.io/),
`queueio.django` is added to `INSTALLED_APPS` automatically.

Otherwise, add it manually:

```python
INSTALLED_APPS = [
    "queueio.django",
    # ...
]
```

This must come **after** whichever app provides the `runserver` command
you want to chain with
(e.g. `daphne`, `django.contrib.staticfiles`),
because Django resolves management commands by last-app-wins order.

### Custom provider

If you use a custom `runserver` provider
like `django.contrib.staticfiles` or `daphne`,
tell queueio which app to chain with:

```toml
[tool.queueio.django]
runserver = "daphne"
```

The value is the app label (or dotted module path).
queueio resolves it to `{value}.management.commands.runserver`
and subclasses that command.
If omitted, it defaults to Django's built-in `runserver`.

### `runserver_plus`

There is also a built-in `runserver_plus` command
that wraps [django-extensions](https://django-extensions.readthedocs.io/)' `runserver_plus`
with `activate()`.
This is available automatically
when `django-extensions` is installed
and `queueio.django` is in `INSTALLED_APPS`.

A complete working example is in `queueio/samples/django/`.
