from django.contrib import admin
from .models import *

admin.site.register(CustomUser)
admin.site.register(SellerProfiles)
admin.site.register(Product)
admin.site.register(ProductImage)
admin.site.register(ProductQuantityPrice)
admin.site.register(Cart)
admin.site.register(Order)
admin.site.register(DeliveryPartnerProfile)
admin.site.register(Delivery)
# Register your models here.
