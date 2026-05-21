
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from .models import Product, OrderItem

def get_restock_insights(seller_profile):
    """
    Analyzes sales history and stock for a seller's products.
    """
    end_date = timezone.now()
    start_date = end_date - timedelta(days=60)

    products = Product.objects.filter(seller=seller_profile)
    insights = []
    total_products = products.count()
    healthy_stock_count = 0

    category_sales = {}

    for product in products:
        if product.product_type == 'piece':
            current_stock = product.stock or 0
        else:
            current_stock = product.quantity_prices.aggregate(total_stock=Sum('stock'))['total_stock'] or 0

        total_sold = OrderItem.objects.filter(
            product=product,
            order__created_at__range=(start_date, end_date),
            order__status__in=['ordered', 'assigned_delivery', 'inprogress', 'packed', 'shipped', 'Delivered']
        ).aggregate(total=Sum('quantity'))['total'] or 0

        cat_name = product.category.CategoryName
        category_sales[cat_name] = category_sales.get(cat_name, 0) + total_sold

        avg_daily_sales = total_sold / 60.0

        if avg_daily_sales > 0:
            stock_out_days = current_stock / avg_daily_sales
        else:
            stock_out_days = 999.0

        performance = "Slow Moving"
        thirty_days_ago = end_date - timedelta(days=30)
        sold_thirty_days = OrderItem.objects.filter(
            product=product,
            order__created_at__range=(thirty_days_ago, end_date),
            order__status__in=['ordered', 'assigned_delivery', 'inprogress', 'packed', 'shipped', 'Delivered']
        ).exists()

        if not sold_thirty_days:
            performance = "Dead Stock"
        elif stock_out_days > 90 and current_stock > 50:
            performance = "Overstocked"
        elif avg_daily_sales > 5:
            performance = "Fast Selling"
        elif avg_daily_sales >= 2:
            performance = "Medium Selling"

        priority = "Low"
        suggestion = "No action needed"
        restock_qty = 0

        if stock_out_days < 5 or current_stock < 10:
            priority = "High"
            restock_qty = int(avg_daily_sales * 15) if avg_daily_sales > 0 else 20
            suggestion = f"Urgent: Restock {restock_qty} units"
        elif stock_out_days < 15:
            priority = "Medium"
            restock_qty = int(avg_daily_sales * 15) if avg_daily_sales > 0 else 10
            suggestion = f"Recommended: Restock {restock_qty} units"
        elif performance == "Overstocked":
            suggestion = "Reduce stock/Promote"

        insights.append({
            "product_id": product.id,
            "product": product.name,
            "category": cat_name,
            "stock": current_stock,
            "avg_daily_sales": round(avg_daily_sales, 2),
            "stock_out_days": round(stock_out_days, 1) if stock_out_days < 999 else "No risk",
            "performance": performance,
            "restock": suggestion,
            "priority": priority,
            "sales_trend": get_product_sales_trend(product, 30),
            "revenue": float(total_sold) * float(product.price * (1 - product.discount / 100))
        })

        if priority == "Low":
            healthy_stock_count += 1

    efficiency_index = int((healthy_stock_count / total_products * 100)) if total_products > 0 else 100

    no_sales_products = [i for i in insights if i['avg_daily_sales'] == 0]
    most_profitable = sorted(insights, key=lambda x: x['revenue'], reverse=True)[:5]
    top_category = max(category_sales.items(), key=lambda x: x[1])[0] if category_sales else "N/A"

    return {
        "insights": insights,
        "efficiency_index": efficiency_index,
        "no_sales_count": len(no_sales_products),
        "most_profitable": most_profitable,
        "top_category": top_category
    }

def get_product_sales_trend(product, days):
    """
    Returns daily sales for the last N days.
    """
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days-1)

    sales_data = OrderItem.objects.filter(
        product=product,
        order__created_at__date__range=(start_date, end_date),
        order__status__in=['ordered', 'assigned_delivery', 'inprogress', 'packed', 'shipped', 'Delivered']
    ).values('order__created_at__date').annotate(total=Sum('quantity')).order_by('order__created_at__date')

    date_map = { (start_date + timedelta(days=i)): 0 for i in range(days) }
    for entry in sales_data:
        date_map[entry['order__created_at__date']] = entry['total']

    return [{"date": d.strftime("%Y-%m-%d"), "sales": v} for d, v in sorted(date_map.items())]
