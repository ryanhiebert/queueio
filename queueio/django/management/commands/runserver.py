import tomllib
from importlib import import_module
from pathlib import Path


def _find_pyproject() -> Path | None:
    for path in [cwd := Path.cwd(), *cwd.parents]:
        candidate = path / "pyproject.toml"
        if candidate.is_file():
            return candidate
    return None


def _queueio_django_config() -> dict:
    if pyproject := _find_pyproject():
        with pyproject.open("rb") as f:
            config = tomllib.load(f)
        return config.get("tool", {}).get("queueio", {}).get("django", {})
    return {}


def _resolve_base_command(config: dict):
    runserver_app = config.get("runserver", "django.core")
    module = import_module(f"{runserver_app}.management.commands.runserver")
    return module.Command


def _build_command():
    base = _resolve_base_command(_queueio_django_config())

    class Command(base):
        def inner_run(self, *args, **options):
            from queueio import activate

            with activate():
                super().inner_run(*args, **options)

    return Command


Command = _build_command()
