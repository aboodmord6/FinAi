from django.core.management.base import BaseCommand
from backend.models import FinancialInstitution


class Command(BaseCommand):
    help = "List all financial institutions"

    def handle(self, *args, **options):
        institutions = FinancialInstitution.objects.all()

        if not institutions.exists():
            self.stdout.write(self.style.WARNING("No financial institutions found."))
            return

        self.stdout.write(
            self.style.SUCCESS(f"Found {institutions.count()} financial institutions:")
        )

        for institution in institutions:
            self.stdout.write(f"- {institution.name}")
