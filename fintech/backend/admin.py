from django.contrib import admin

# Register your models here.
from .models import *

admin.site.register(FinancialInstitution)
admin.site.register(ProductCategory)
admin.site.register(FinancialProduct)
admin.site.register(Fee)
admin.site.register(FXRate)
admin.site.register(Address)  # Assuming Address is also a model you want to register
admin.site.register(Accounts)


