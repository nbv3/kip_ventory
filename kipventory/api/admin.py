from django.contrib import admin

from . import models

# Register your models here.
admin.site.register(models.Item)
admin.site.register(models.Tag)
admin.site.register(models.CustomField)
# admin.site.register(models.CartItem)
admin.site.register(models.CustomValue)
# admin.site.register(models.NewUserRequest)
admin.site.register(models.Transaction)
admin.site.register(models.Request)
admin.site.register(models.RequestedItem)
admin.site.register(models.Disbursement)
admin.site.register(models.Loan)
