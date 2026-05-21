
import random

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.conf import settings
PHONE_REGEX = RegexValidator(
    regex=r'^\d{10}$',
    message="Phone number must be exactly 10 digits."
)

class CustomUser(AbstractUser):


    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=10, validators=[PHONE_REGEX], blank=True, null=True)
    user_type = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.username} ({self.user_type})"

class SellerProfiles(models.Model):



    seller = models.OneToOneField(CustomUser, on_delete=models.CASCADE)

    display_name = models.CharField(max_length=200)

    address = models.TextField()
    city = models.CharField(max_length=100)

    opening_time = models.TimeField()
    closing_time = models.TimeField()

    document = models.FileField(upload_to='documents/')

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_name
class CustomerProfile(models.Model):

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)

    full_name = models.CharField(max_length=150)

    phone = models.CharField(max_length=10, validators=[PHONE_REGEX])

    address = models.TextField()

    city = models.CharField(max_length=100)

    latitude = models.FloatField()

    longitude = models.FloatField()

    reward_points = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class DeliveryPartnerProfile(models.Model):

    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)

    full_name = models.CharField(max_length=150)

    phone = models.CharField(max_length=10, validators=[PHONE_REGEX])

    vehicle_type = models.CharField(max_length=50)

    vehicle_number = models.CharField(max_length=50)

    working_city = models.CharField(max_length=100)

    address = models.TextField()

    latitude = models.FloatField(null=True, blank=True)

    longitude = models.FloatField(null=True, blank=True)

    is_available = models.BooleanField(default=True)
    is_active=models.BooleanField(default=False,blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name

class Category(models.Model):
        seller = models.ForeignKey(SellerProfiles, on_delete=models.CASCADE)
        CategoryName = models.CharField(max_length=20)

        def __str__(self):
            return self.CategoryName

class Brands(models.Model):
    seller = models.ForeignKey(SellerProfiles, on_delete=models.CASCADE)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    brandName=models.CharField(max_length=15)

    def __str__(self):
        return self.brandName

class Product(models.Model):
    PRODUCT_TYPE = (
        ('quantity', 'Quantity Based'),
        ('piece', 'Piece Based'),
    )

    seller = models.ForeignKey(SellerProfiles, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    short_description = models.CharField(max_length=255)
    description = models.TextField()

    product_type = models.CharField(max_length=10, choices=PRODUCT_TYPE, default='piece')

    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)

    stock = models.PositiveIntegerField(null=True, blank=True)

    is_featured = models.BooleanField(default=False)
    is_new = models.BooleanField(default=True)
    expiry = models.CharField(max_length=30)

    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    brand = models.ForeignKey(Brands, on_delete=models.CASCADE)
    lead_time = models.PositiveIntegerField(default=7)
    sales_count = models.PositiveIntegerField(default=0)
    priority_level = models.CharField(max_length=20, choices=[('essential', 'Essential'), ('optional', 'Optional')], default='optional')

    def __str__(self):
        return self.name

class ProductImage(models.Model):
    product = models.ForeignKey(Product, related_name='images',
                                on_delete=models.CASCADE)
    image = models.ImageField(upload_to='product_images/')

    def __str__(self):
        return f"Image for {self.product.name}"

class ProductQuantityPrice(models.Model):
    product = models.ForeignKey(Product, related_name="quantity_prices", on_delete=models.CASCADE)
    quantity = models.CharField(max_length=20)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"



class Review(models.Model):
    product = models.ForeignKey(Product, related_name='reviews', on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review by {self.user.username} - {self.rating}★"
class Wishlist(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'product')

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"

class Cart(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    shared_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="shared_cart_items")

    size = models.CharField(
        max_length=2,
        blank=True,
        null=True
    )

    weight = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True
    )
    weight_unit = models.CharField(
        max_length=2,
        blank=True,
        null=True
    )
    price=models.DecimalField(max_digits=6,
        decimal_places=2,
        blank=True,
        null=True)

    class Meta:
        unique_together = (
            'user',
            'product',
            'price',
            'size',
            'weight',
            'weight_unit',
        )


def __str__(self):
    if self.weight:
        return f"{self.product.name} {self.weight}{self.weight_unit} × {self.quantity}"
    return f"{self.product.name} × {self.quantity}"


class Order(models.Model):
    PAYMENT_CHOICES = (
        ('COD', 'Cash on Delivery'),
        ('ONLINE', 'Online Payment'),
    )
    STATUS_CHOICES=(
        ("ordered","ordered"),
        ("assigned_delivery", "assigned_delivery"),
        ("Rejected","Rejected"),
        ("inprogress","inprogress"),
        ("packed","packed"),
        ("shipped","shipped"),
        ("Returned","Returned"),
        ("Cancelled","Cancelled"),
        ("Delivered","Delivered")
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    city = models.CharField(max_length=50)
    postal_code = models.CharField(max_length=10)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='COD')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2,blank=True,default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    status=models.CharField(max_length=10,default="ordered")
    delivery_partner = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_orders"
    )
    otp=models.CharField(max_length=6,blank=True)

    def __str__(self):
        return f"Order {self.id} by {self.user.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class Complaint(models.Model):
    PRIORITY_CHOICES = (
        ('HIGH', 'HIGH'),
        ('MEDIUM', 'MEDIUM'),
        ('LOW', 'LOW'),
    )
    STATUS_CHOICES = (
        ('Pending', 'Pending'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
    )

    customer = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200, default="Complaint")
    text = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='LOW')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            self.priority = self.assign_priority(self.text)
        super().save(*args, **kwargs)

    def assign_priority(self, text):
        from .ai_complaint_priority import analyze_complaint_text
        return analyze_complaint_text(text)

    def __str__(self):
        return f"Complaint {self.id} - {self.priority}"


class BrowsingHistory(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} viewed {self.product.name}"

class DeliverySlot(models.Model):
    SLOT_TIME = (
        ('8 AM – 10 AM', '8 AM – 10 AM'),
        ('10 AM – 12 PM', '10 AM – 12 PM'),
        ('2 PM – 4 PM', '2 PM – 4 PM'),
        ('6 PM – 8 PM', '6 PM – 8 PM'),
    )
    time_slot = models.CharField(max_length=50, choices=SLOT_TIME)
    date = models.DateField()
    max_orders = models.PositiveIntegerField(default=10)
    current_orders = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('time_slot', 'date')

    def is_available(self):
        return self.current_orders < self.max_orders

    def __str__(self):
        return f"{self.date} | {self.time_slot}"

class DeliveryAgent(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    vehicle_number = models.CharField(max_length=20, blank=True, null=True)
    is_available = models.BooleanField(default=True)
    current_lat = models.FloatField(default=12.9716)
    current_lng = models.FloatField(default=77.5946)

    def __str__(self):
        return self.name

class Delivery(models.Model):
    TRAFFIC_LEVEL = (
        ('LOW', 'Low Traffic (1.0x)'),
        ('MEDIUM', 'Medium Traffic (1.5x)'),
        ('HIGH', 'Heavy Traffic (2.0x)'),
    )
    STATUS_CHOICES = (
        ('PACKED', 'Order Packed'),
        ('DISPATCHED', 'Out for Delivery'),
        ('NEARBY', 'Nearby'),
        ('DELIVERED', 'Delivered'),
    )
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery')
    slot = models.ForeignKey(DeliverySlot, on_delete=models.SET_NULL, null=True)
    agent = models.ForeignKey(DeliveryPartnerProfile, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PACKED')
    traffic_level = models.CharField(max_length=10, choices=TRAFFIC_LEVEL, default='LOW')
    distance_km = models.FloatField(default=5.0)
    predicted_eta = models.PositiveIntegerField(null=True, blank=True)
    is_notified = models.BooleanField(default=False)

    def __str__(self):
        return f"Delivery for Order"

class DeliveryTracking(models.Model):
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name='tracking_logs')
    status = models.CharField(max_length=50)
    location_name = models.CharField(max_length=100, blank=True)
    lat = models.FloatField()
    lng = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tracking Log for {self.delivery.order.id} at {self.timestamp}"


class Notification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=100)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"


class Vendor(models.Model):
    vendor_name = models.CharField(max_length=100)
    location = models.CharField(max_length=100, blank=True, null=True)
    rating = models.FloatField(default=0.0)

    def __str__(self):
        return self.vendor_name

class VendorPrice(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='vendor_prices')
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage discount (e.g. 5 for 5%)", default=0.0)
    stock = models.PositiveIntegerField(default=10)
    last_updated = models.DateTimeField(auto_now=True)

    @property
    def final_price(self):
        return self.price * (1 - self.discount / 100)

    def __str__(self):
        return f"{self.vendor.vendor_name} - {self.product.name}"




class UserPantry(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='pantry_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.FloatField(default=0.0)
    unit = models.CharField(max_length=20, default='packs')
    last_updated = models.DateTimeField(auto_now=True)
    threshold = models.FloatField(default=2.0)

    def __str__(self):
        return f"{self.user.username} - {self.product.name} ({self.quantity} {self.unit})"

class PantryUsage(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    usage_date = models.DateField(auto_now_add=True)
    quantity_used = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.user.username} used {self.quantity_used} of {self.product.name}"

class SeasonalPack(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    image = models.ImageField(upload_to='seasonal_packs/', null=True, blank=True)
    products = models.ManyToManyField(Product)
    discount_percentage = models.FloatField(default=10.0)
    is_active = models.BooleanField(default=True)
    festival_name = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.name

class FamilyGroup(models.Model):
    admin = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="family_admin")
    group_name = models.CharField(max_length=100)
    group_code = models.CharField(max_length=10, unique=True)
    members = models.ManyToManyField(CustomUser, related_name="family_groups")

    def __str__(self):
        return self.group_name
