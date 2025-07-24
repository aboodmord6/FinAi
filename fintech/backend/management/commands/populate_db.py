# This file will contain the management command to populate the database.
# finance/management/commands/populate_db.py

import random
import csv
import os
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker
from django.contrib.auth import get_user_model
from django.conf import settings

# Make sure to import all your models
from backend.models import (
    Address,
    FinancialInstitution,
    ProductCategory,
    FinancialProduct,
    Fee,
    FXRate,
    Accounts,
)

User = get_user_model()

# Configuration
NUM_ACCOUNTS_PER_INSTITUTION = 20
NUM_PRODUCTS_PER_INSTITUTION = 5
NUM_FEES_PER_PRODUCT = 3
NUM_FX_RATES_PER_INSTITUTION = 4
NUM_USERS = 50  # Number of users to create


class Command(BaseCommand):
    help = "Populates the database with realistic sample data for financial comparison models using real Jordan banks data."

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write("Starting database population...")

        # Initialize Faker
        self.faker = Faker()

        # Clear existing data
        self.clear_data()

        # Create new data
        self.create_users()
        self.create_addresses_and_institutions()
        self.create_product_categories()
        self.create_financial_products()
        self.create_fees()
        self.create_fx_rates()
        self.create_accounts()

        self.stdout.write(self.style.SUCCESS("Database successfully populated!"))

    def clear_data(self):
        self.stdout.write("Clearing existing data...")
        # Delete in reverse order of creation to respect foreign key constraints
        Accounts.objects.all().delete()
        FXRate.objects.all().delete()
        Fee.objects.all().delete()
        FinancialProduct.objects.all().delete()
        ProductCategory.objects.all().delete()
        FinancialInstitution.objects.all().delete()
        Address.objects.all().delete()
        # Note: We're not deleting users as they might be needed for other purposes
        # If you want to clear users too, uncomment the next line
        # User.objects.filter(is_superuser=False).delete()  # Keep superuser accounts
        self.stdout.write(self.style.SUCCESS("Data cleared."))

    def create_users(self):
        """Create sample users for account linking"""
        self.stdout.write("Creating sample users...")

        # Check if we already have enough users
        existing_users = User.objects.filter(is_superuser=False).count()
        if existing_users >= NUM_USERS:
            self.stdout.write(
                f"  - Already have {existing_users} users. Skipping user creation."
            )
            return

        users_to_create = NUM_USERS - existing_users
        users = []

        # Common Jordanian first names
        jordanian_first_names = [
            "Ahmed",
            "Mohammed",
            "Omar",
            "Ali",
            "Hassan",
            "Khaled",
            "Youssef",
            "Saeed",
            "Fadi",
            "Tariq",
            "Fatima",
            "Amina",
            "Layla",
            "Nour",
            "Sara",
            "Reem",
            "Dina",
            "Rana",
            "Lina",
            "Hala",
            "Abdullah",
            "Mahmoud",
            "Nasser",
            "Waleed",
            "Jamal",
            "Sami",
            "Rami",
            "Zaid",
            "Marwan",
            "Basel",
        ]

        # Common Jordanian last names
        jordanian_last_names = [
            "Al-Ahmad",
            "Al-Mohammed",
            "Al-Omar",
            "Al-Hassan",
            "Al-Khouri",
            "Qasemi",
            "Nabulsi",
            "Hijazi",
            "Masri",
            "Shami",
            "Khoury",
            "Haddad",
            "Mansour",
            "Saleh",
            "Nasser",
            "Farah",
            "Zayed",
            "Khalil",
            "Abdallah",
            "Ibrahim",
            "Yousef",
            "Mahmoud",
            "Said",
            "Rashid",
            "Hamdan",
            "Najjar",
            "Awad",
            "Karam",
        ]

        # Get existing usernames and emails to avoid duplicates
        existing_usernames = set(User.objects.values_list("username", flat=True))
        existing_emails = set(User.objects.values_list("email", flat=True))

        created_count = 0
        attempts = 0
        max_attempts = users_to_create * 3  # Prevent infinite loop

        while created_count < users_to_create and attempts < max_attempts:
            attempts += 1

            first_name = self.faker.random_element(jordanian_first_names)
            last_name = self.faker.random_element(jordanian_last_names)

            # Create unique username with random number
            base_username = f"{first_name.lower()}.{last_name.lower().replace('-', '').replace('al', '')}"
            username = f"{base_username}{self.faker.random_int(min=1, max=9999)}"

            # Create unique email
            domain = self.faker.random_element(
                ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]
            )
            email = f"{username}@{domain}"

            # Check if username and email are unique
            if username not in existing_usernames and email not in existing_emails:
                existing_usernames.add(username)
                existing_emails.add(email)

                users.append(
                    User(
                        username=username,
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        is_active=True,
                        is_staff=False,
                        is_superuser=False,
                    )
                )
                created_count += 1

        # Bulk create users
        created_users = User.objects.bulk_create(users)

        # Set passwords for created users (bulk_create doesn't handle password hashing)
        for user in created_users:
            user.set_password("password123")  # Default password for all test users
            user.save()

        self.stdout.write(
            f"  - Created {len(created_users)} sample users with default password 'password123'."
        )
        if attempts >= max_attempts and created_count < users_to_create:
            self.stdout.write(
                self.style.WARNING(f"  - Could only create {created_count} users after {attempts} attempts.")
            )

    def read_jordan_banks_csv(self):
        """Read the Jordan banks data from CSV file"""
        csv_path = os.path.join(settings.BASE_DIR.parent, "banksjordan.csv")
        banks_data = []

        try:
            with open(csv_path, "r", encoding="utf-8") as file:
                csv_reader = csv.DictReader(file)
                for row in csv_reader:
                    # Parse location to extract city and area
                    location = row["Headquarter Location"]
                    if " - " in location:
                        city, area = location.split(" - ", 1)
                    else:
                        city = location
                        area = "Central"

                    banks_data.append(
                        {
                            "name": row["Bank Name"],
                            "website": row["Website"] if row["Website"] else None,
                            "city": city.strip(),
                            "area": area.strip(),
                        }
                    )

            self.stdout.write(f"Successfully loaded {len(banks_data)} banks from CSV")
            return banks_data

        except FileNotFoundError:
            self.stdout.write(
                self.style.ERROR(
                    f"CSV file not found at {csv_path}. Using fallback data."
                )
            )
            return self.get_fallback_banks_data()
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error reading CSV: {e}. Using fallback data.")
            )
            return self.get_fallback_banks_data()

    def get_fallback_banks_data(self):
        """Fallback bank data in case CSV can't be read"""
        return [
            {
                "name": "Arab Bank",
                "website": "https://arabbank.com.jo",
                "city": "Amman",
                "area": "Shmeisani",
            },
            {
                "name": "Bank of Jordan",
                "website": "https://bankofjordan.com",
                "city": "Amman",
                "area": "Abdali",
            },
            {
                "name": "Cairo Amman Bank",
                "website": "https://cab.jo",
                "city": "Amman",
                "area": "Wadi Saqra",
            },
            {
                "name": "Capital Bank of Jordan",
                "website": "https://capitalbank.jo",
                "city": "Amman",
                "area": "Shmeisani",
            },
            {
                "name": "Housing Bank for Trade & Finance",
                "website": "https://hbtf.com",
                "city": "Amman",
                "area": "Shmeisani",
            },
            {
                "name": "Jordan Commercial Bank",
                "website": "https://jcbank.com.jo",
                "city": "Amman",
                "area": "Shmeisani",
            },
            {
                "name": "Jordan Kuwait Bank",
                "website": "https://www.jkb.com",
                "city": "Amman",
                "area": "Shmeisani",
            },
            {
                "name": "Jordan Ahli Bank",
                "website": "https://ahli.com",
                "city": "Amman",
                "area": "Abdali",
            },
        ]

    def create_addresses_and_institutions(self):
        self.stdout.write(
            "Creating Addresses and Financial Institutions using Jordan banks data..."
        )

        # Read Jordan banks data from CSV
        jordan_banks = self.read_jordan_banks_csv()

        # Create addresses for each bank
        addresses = []
        for bank_data in jordan_banks:
            addresses.append(
                Address(
                    country="Jordan",
                    city=bank_data["city"],
                    street=self.faker.street_address(),
                    area=bank_data["area"],
                    state="Amman",
                    postcode=self.faker.postcode(),
                    country_code="JO",
                    latitude=31.9566
                    + random.uniform(-0.1, 0.1),  # Amman latitude with small variation
                    longitude=35.9457
                    + random.uniform(-0.1, 0.1),  # Amman longitude with small variation
                )
            )
        Address.objects.bulk_create(addresses)
        self.stdout.write(f"  - Created {len(addresses)} Addresses.")

        # Get all created addresses to link them
        all_addresses = list(Address.objects.all())

        # Create financial institutions using real Jordan bank data
        institutions = []
        for i, bank_data in enumerate(jordan_banks):
            # Determine institution type based on bank name
            institution_type = "Bank"
            if (
                "digital" in bank_data["name"].lower()
                or "fintech" in bank_data["name"].lower()
            ):
                institution_type = "Fintech"
            elif "islamic" in bank_data["name"].lower():
                institution_type = "Islamic Bank"
            elif "central" in bank_data["name"].lower():
                institution_type = "Central Bank"

            # Generate contact email based on bank name
            clean_name = (
                bank_data["name"]
                .lower()
                .replace(" ", "")
                .replace("&", "")
                .replace("-", "")
            )
            contact_email = f"contact@{clean_name[:15]}.jo"

            institutions.append(
                FinancialInstitution(
                    name=bank_data["name"],
                    website_url=bank_data["website"],
                    contact_email=contact_email,
                    contact_phone=f"+962 6 {random.randint(4000000, 5999999)}",  # Jordan phone format
                    address=(
                        all_addresses[i]
                        if i < len(all_addresses)
                        else random.choice(all_addresses)
                    ),
                    InstitutionType=institution_type,
                    BIC_code=self.faker.swift(length=8),
                )
            )
        FinancialInstitution.objects.bulk_create(institutions)
        self.stdout.write(
            f"  - Created {len(institutions)} Financial Institutions using real Jordan banks data."
        )

    def create_product_categories(self):
        self.stdout.write("Creating Product Categories...")
        categories_data = [
            {
                "name": "Current Accounts",
                "description": "Accounts for daily transactions.",
                "level": 1,
            },
            {
                "name": "Savings Accounts",
                "description": "Accounts for saving money and earning interest.",
                "level": 1,
            },
            {
                "name": "Credit Cards",
                "description": "Cards for credit-based purchases.",
                "level": 1,
            },
            {
                "name": "Personal Loans",
                "description": "Unsecured loans for personal use.",
                "level": 1,
            },
            {
                "name": "Mortgages",
                "description": "Loans for purchasing property.",
                "level": 1,
            },
        ]
        categories = [
            ProductCategory(
                name=cat["name"],
                description=cat["description"],
                product_node_level=cat["level"],
            )
            for cat in categories_data
        ]
        ProductCategory.objects.bulk_create(categories)
        self.stdout.write(f"  - Created {len(categories)} Product Categories.")

    def create_financial_products(self):
        self.stdout.write("Creating Financial Products...")
        institutions = list(FinancialInstitution.objects.all())
        categories = list(ProductCategory.objects.all())
        products = []

        product_templates = {
            "Current Accounts": ["Standard", "Gold", "Student", "Business"],
            "Savings Accounts": ["Easy Saver", "High-Interest", "Junior ISA"],
            "Credit Cards": ["Platinum Rewards", "Low Rate", "Cashback", "Travel"],
            "Personal Loans": ["Standard Loan", "Car Loan", "Debt Consolidation"],
            "Mortgages": ["Fixed Rate Mortgage", "Variable Rate Mortgage"],
        }

        for inst in institutions:
            for _ in range(NUM_PRODUCTS_PER_INSTITUTION):
                category = random.choice(categories)
                template_name = random.choice(
                    product_templates.get(category.name, ["Generic"])
                )

                commercial_name = f"{template_name} Account"
                if category.name == "Credit Cards":
                    commercial_name = f"{template_name} Card"
                elif "Loan" in category.name or "Mortgage" in category.name:
                    commercial_name = f"{template_name}"

                products.append(
                    FinancialProduct(
                        FinancialInstitution=inst,
                        category=category,
                        product_id=f"PROD-{inst.id}-{self.faker.uuid4()[:8]}",
                        commercial_name=commercial_name,
                        type=category.name.replace(" ", ""),
                        description=self.faker.sentence(nb_words=15),
                        details={
                            "min_balance": round(random.uniform(0, 500), 2),
                            "interest_rate_apy": round(random.uniform(0.1, 5.5), 3),
                            "features": self.faker.bs().split(" "),
                        },
                    )
                )
        FinancialProduct.objects.bulk_create(products)
        self.stdout.write(f"  - Created {len(products)} Financial Products.")

    def create_fees(self):
        self.stdout.write("Creating Fees...")
        products = list(FinancialProduct.objects.all())
        fees = []

        fee_services = [
            "Monthly Maintenance",
            "ATM Withdrawal (Own Network)",
            "ATM Withdrawal (Other Network)",
            "Overdraft Fee",
            "International Transfer",
        ]
        service_channels = ["Branch", "ATM", "Online", "Mobile App"]
        fee_types = ["Fixed", "Percentage", "Variable"]

        for prod in products:
            for _ in range(random.randint(1, NUM_FEES_PER_PRODUCT)):
                service = random.choice(fee_services)
                fees.append(
                    Fee(
                        product=prod,
                        fee_id=f"FEE-{prod.id}-{self.faker.uuid4()[:6]}",
                        service_channel=random.choice(service_channels),
                        service=service,
                        category="Standard",
                        amount=Decimal(random.randrange(500, 5000))
                        / 100,  # e.g., 5.00 to 50.00
                        currency="JOD",
                        additional_info=f"Fee for {service.lower()}.",
                        fee_type=random.choice(fee_types),
                        applicable_for_institutions=[],
                        last_modification_date_time=timezone.now(),
                    )
                )
        Fee.objects.bulk_create(fees)
        self.stdout.write(f"  - Created {len(fees)} Fees.")

    def create_fx_rates(self):
        self.stdout.write("Creating FX Rates...")
        institutions = list(FinancialInstitution.objects.all())
        rates = []

        currency_pairs = [
            ("USD", "JOD"),
            ("EUR", "JOD"),
            ("GBP", "JOD"),
            ("SAR", "JOD"),
        ]

        for inst in institutions:
            for _ in range(NUM_FX_RATES_PER_INSTITUTION):
                source, target = random.choice(currency_pairs)

                # Base rate for JOD pairs
                base_rate = 0.709 if source == "USD" else random.uniform(0.75, 0.95)

                conversion_val = Decimal(
                    base_rate + random.uniform(-0.05, 0.05)
                ).quantize(Decimal("0.000001"))
                inverse_val = (Decimal(1) / conversion_val).quantize(
                    Decimal("0.000001")
                )

                rates.append(
                    FXRate(
                        FinancialInstitution=inst,
                        source_currency=source,
                        target_currency=target,
                        conversion_value=conversion_val,
                        inverse_conversion_value=inverse_val,
                        effective_date=timezone.now(),
                        last_effective_date_time=timezone.now(),
                        min_conversion_value=conversion_val * Decimal("0.99"),
                        max_conversion_value=conversion_val * Decimal("1.01"),
                    )
                )
        FXRate.objects.bulk_create(rates)
        self.stdout.write(f"  - Created {len(rates)} FX Rates.")

    def create_accounts(self):
        self.stdout.write("Creating Accounts...")
        institutions = list(FinancialInstitution.objects.all())
        products = list(FinancialProduct.objects.all())
        users = list(User.objects.all())
        accounts = []

        if not users:
            self.stdout.write(
                self.style.WARNING("No users found. Skipping account creation.")
            )
            return

        # Calculate accounts per institution based on actual number of institutions
        accounts_per_inst = (
            max(1, NUM_ACCOUNTS_PER_INSTITUTION // len(institutions))
            if institutions
            else 1
        )

        for inst in institutions:
            for _ in range(accounts_per_inst):
                product = random.choice(products)
                user = random.choice(users)
                accounts.append(
                    Accounts(
                        user=user,
                        financial_institution=inst,
                        product=product,
                        account_id=f"ACC-{inst.id}-{self.faker.uuid4()[:12]}",
                        account_status=random.choice(["active", "inactive", "closed"]),
                        account_currency="JOD",
                        available_balance=Decimal(random.uniform(100, 50000)).quantize(
                            Decimal("0.01")
                        ),
                    )
                )
        Accounts.objects.bulk_create(accounts)
        self.stdout.write(f"  - Created {len(accounts)} Accounts.")
