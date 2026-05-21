import datetime
import math
from django.utils import timezone
from .models import UserPantry, PantryUsage, Product, CustomUser, Notification

def get_user_pantry(user_id):
    """
    Returns all items currently in the user's pantry.
    """
    return UserPantry.objects.filter(user_id=user_id)

def calculate_daily_usage(user_id, product_id):
    """
    Calculates the average daily usage of a product based on the last 30 days of data.
    """
    thirty_days_ago = timezone.now().date() - datetime.timedelta(days=30)
    usages = PantryUsage.objects.filter(
        user_id=user_id, 
        product_id=product_id,
        usage_date__gte=thirty_days_ago
    )
    
    if not usages.exists():
        # Fallback default if no history exists (0.05 units per day)
        return 0.05
        
    total_used = sum(u.quantity_used for u in usages)
    
    # Calculate daily usage assuming 30 days window
    daily_usage = total_used / 30.0
    return round(daily_usage, 3)

def predict_days_remaining(user_id, product_id):
    """
    Predicts how many days the current stock will last.
    """
    pantry_item = UserPantry.objects.filter(user_id=user_id, product_id=product_id).first()
    if not pantry_item or pantry_item.quantity <= 0:
        return 0
        
    daily_usage = calculate_daily_usage(user_id, product_id)
    if daily_usage <= 0:
        return 999  # Effectively infinite
        
    days_left = pantry_item.quantity / daily_usage
    return int(math.floor(days_left))

def detect_low_stock(user_id):
    """
    Detects which items in the pantry are running out.
    """
    alerts = []
    pantry_items = get_user_pantry(user_id)
    
    for item in pantry_items:
        # Check hard threshold
        if item.quantity < item.threshold:
            alerts.append({
                "product_id": item.product.id,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "unit": item.unit,
                "reason": f"Only {item.quantity} {item.unit} remaining.",
                "type": "danger"
            })
            continue
            
        # Check AI predicted days remaining
        days_left = predict_days_remaining(user_id, item.product.id)
        if days_left <= 3:
            alerts.append({
                "product_id": item.product.id,
                "product_name": item.product.name,
                "quantity": item.quantity,
                "unit": item.unit,
                "reason": f"Estimated to run out in {days_left} days.",
                "type": "warning"
            })
            
    return alerts

def generate_reorder_alerts(user_id):
    """
    Checks low stock and sends actual system notifications if not sent recently.
    """
    alerts = detect_low_stock(user_id)
    user = CustomUser.objects.get(id=user_id)
    
    for alert in alerts:
        # Prevent spam: only create if no similar notification exists today
        today = timezone.now().date()
        title = f"{alert['product_name']} is running low!"
        
        recent_notif = Notification.objects.filter(
            user=user, 
            title=title,
            created_at__date=today
        ).exists()
        
        if not recent_notif:
            Notification.objects.create(
                user=user,
                title=title,
                message=f"Smart Pantry Alert: {alert['reason']} Tap to restock now."
            )
            
    return alerts

def auto_update_pantry_on_order(user, order):
    """
    Automatically adds purchased items to the user's pantry.
    """
    for order_item in order.items.all():
        try:
            pantry_item, created = UserPantry.objects.get_or_create(
                user=user, 
                product=order_item.product,
                defaults={'quantity': 0, 'unit': 'units', 'threshold': 1.0}
            )
            pantry_item.quantity += float(order_item.quantity)
            pantry_item.save()
        except Exception as e:
            print(f"Error updating pantry: {str(e)}")
