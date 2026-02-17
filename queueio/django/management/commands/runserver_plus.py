from django_extensions.management.commands.runserver_plus import Command as BaseCommand

from queueio import activate


class Command(BaseCommand):
    def inner_run(self, options):
        with activate():
            super().inner_run(options)
