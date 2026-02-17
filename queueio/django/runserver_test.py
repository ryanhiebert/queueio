import os
import sysconfig

import pytest

from .management.commands.runserver import _build_command


@pytest.mark.parametrize(
    ("runserver_app", "expected_module"),
    [
        pytest.param(
            None,
            "django.core.management.commands.runserver",
            id="default",
        ),
        pytest.param(
            "django.contrib.staticfiles",
            "django.contrib.staticfiles.management.commands.runserver",
            id="staticfiles",
        ),
        pytest.param(
            "daphne",
            "daphne.management.commands.runserver",
            id="daphne",
            marks=pytest.mark.skipif(
                bool(sysconfig.get_config_var("Py_GIL_DISABLED")),
                reason="zope.interface re-enables the GIL on free-threaded builds",
            ),
        ),
    ],
)
def test_runserver(tmp_path, runserver_app, expected_module):
    config = "[tool.queueio]\n"
    if runserver_app is not None:
        config = f'[tool.queueio.django]\nrunserver = "{runserver_app}"\n'

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(config)

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        Cmd = _build_command()
        from importlib import import_module

        expected = import_module(expected_module)
        assert issubclass(Cmd, expected.Command)
    finally:
        os.chdir(original_cwd)


def test_runserver_plus():
    from django.conf import settings

    if not settings.configured:
        settings.configure()

    from django_extensions.management.commands import runserver_plus as expected

    from .management.commands.runserver_plus import Command

    assert issubclass(Command, expected.Command)
