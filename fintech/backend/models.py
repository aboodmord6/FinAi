from django.db import models
from django.contrib.auth import get_user_model


class Accounts(models.Model):
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="accounts"
    )
    financial_institution = models.ForeignKey(
        "FinancialInstitution", on_delete=models.CASCADE
    )
    product = models.ForeignKey(
        "FinancialProduct", on_delete=models.CASCADE, null=True, blank=True
    )
    account_id = models.CharField(max_length=100, unique=True)
    account_status = models.CharField(max_length=50, blank=True)
    account_currency = models.CharField(max_length=10, blank=True)
    available_balance = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    def __str__(self):
        return f"{self.user.username} ({self.financial_institution.name})"


class Address(models.Model):
    country = models.CharField(max_length=50)
    city = models.CharField(max_length=50)
    street = models.CharField(max_length=100)
    area = models.CharField(max_length=100, blank=True)  # e.g., Wadi Saqra
    state = models.CharField(max_length=50, blank=True)
    postcode = models.CharField(max_length=20)
    country_code = models.CharField(max_length=2)  # e.g., JO
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )

    def __str__(self):
        return f"{self.street}, {self.area}, {self.city}, {self.country}"


# --- MVP Financial Comparison Models ---


class FinancialInstitution(models.Model):
    name = models.CharField(max_length=100)
    website_url = models.URLField(blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.ForeignKey(
        Address, on_delete=models.CASCADE, null=True, blank=True
    )
    InstitutionType = models.CharField(max_length=20, blank=True, null=True)
    BIC_code = models.CharField(
        max_length=20, blank=True, null=True
    )  # e.g., BIC code for banks

    def __str__(self):
        return self.name


class ProductCategory(models.Model):
    name = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    product_node_level = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name


class FinancialProduct(models.Model):
    FinancialInstitution = models.ForeignKey(
        FinancialInstitution, on_delete=models.CASCADE
    )
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE)
    product_id = models.CharField(max_length=100, unique=True)
    commercial_name = models.CharField(max_length=100)
    type = models.CharField(max_length=50)
    description = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)  # Flexible for API fields

    def __str__(self):
        return f"{self.commercial_name} ({self.FinancialInstitution.name})"


class Fee(models.Model):
    product = models.ForeignKey(FinancialProduct, on_delete=models.CASCADE)
    fee_id = models.CharField(max_length=100)
    service_channel = models.CharField(max_length=50, blank=True)
    service = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=50, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10)
    additional_info = models.TextField(blank=True)
    fee_type = models.CharField(max_length=50, blank=True)
    applicable_for_institutions = models.JSONField(default=list, blank=True)
    last_modification_date_time = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.service} - {self.amount} {self.currency}"


class FXRate(models.Model):
    FinancialInstitution = models.ForeignKey(
        FinancialInstitution, on_delete=models.CASCADE
    )
    source_currency = models.CharField(max_length=10)
    target_currency = models.CharField(max_length=10)
    conversion_value = models.DecimalField(max_digits=16, decimal_places=6)
    inverse_conversion_value = models.DecimalField(max_digits=16, decimal_places=6)
    effective_date = models.DateTimeField()
    last_effective_date_time = models.DateTimeField(null=True, blank=True)
    min_conversion_value = models.DecimalField(
        max_digits=16, decimal_places=6, null=True, blank=True
    )
    max_conversion_value = models.DecimalField(
        max_digits=16, decimal_places=6, null=True, blank=True
    )

    def __str__(self):
        return (
            f"{self.source_currency}/{self.target_currency} @ {self.conversion_value}"
        )


class ChatMemory(models.Model):
    """Store chat conversation history for users."""

    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="chat_memories"
    )
    message_type = models.CharField(
        max_length=10, choices=[("user", "User"), ("assistant", "Assistant")]
    )
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    session_id = models.CharField(
        max_length=100, blank=True, null=True
    )  # For grouping conversations

    class Meta:
        ordering = ["timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["session_id", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.message_type} - {self.timestamp}"
