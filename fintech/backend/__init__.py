# Type hints for Django models
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from .models import FXRate, FinancialInstitution, Accounts, FinancialProduct
