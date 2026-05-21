import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from django.db.models import Sum, Count, Avg
from django.utils import timezone
from datetime import timedelta
from .models import OrderItem, Order, Product, SellerProfiles, Review

def analyze_seller_ai(seller_id):
    seller = SellerProfiles.objects.get(id=seller_id)
    
    # Get all orders for this seller
    order_items = OrderItem.objects.filter(product__seller=seller)
    orders = Order.objects.filter(items__product__seller=seller).distinct().order_by('created_at')
    
    if not orders.exists():
        return {
            'error': 'No sales data available for this seller.',
            'seller_name': seller.display_name
        }

    # Prepare historical data for trends
    data = []
    for o in orders:
        # Sum items for this seller in this order
        revenue = OrderItem.objects.filter(order=o, product__seller=seller).aggregate(total=Sum('price'))['total'] or 0
        data.append({
            'date': o.created_at,
            'revenue': float(revenue),
            'orders': 1
        })
    
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    df.set_index('date', inplace=True)
    
    # Monthly Aggregation (using 'ME' for Month End as per newer pandas version requirements)
    monthly_df = df.resample('ME').agg({'revenue': 'sum', 'orders': 'count'})
    
    # 1. Revenue Trends
    current_month_rev = monthly_df.iloc[-1]['revenue'] if len(monthly_df) > 0 else 0
    prev_month_rev = monthly_df.iloc[-2]['revenue'] if len(monthly_df) > 1 else 0
    
    growth = 0
    if prev_month_rev > 0:
        growth = ((current_month_rev - prev_month_rev) / prev_month_rev) * 100
    
    # Calculate rating early as it's used in prediction
    avg_rating = Review.objects.filter(product__seller=seller).aggregate(Avg('rating'))['rating__avg'] or 3.5
    
    # 2. AI Prediction (Next Month Revenue)
    prediction = 0
    if len(monthly_df) >= 2:
        X = np.array(range(len(monthly_df))).reshape(-1, 1)
        y = monthly_df['revenue'].values
        model = LinearRegression()
        model.fit(X, y)
        next_month_idx = np.array([[len(monthly_df)]])
        prediction = max(0, model.predict(next_month_idx)[0])
    else:
        # For new sellers with only 1 month of data, 
        # project a baseline growth based on rating vs 3.5 stars
        rating_impact = (avg_rating - 3.5) * 0.04 # +/- 4% per star
        prediction = current_month_rev * (1.05 + rating_impact) # Base 5% organic growth
        
    # 3. Performance Score (out of 100)
    # Ratings weight: 30%, Growth: 30%, Volume: 40%
    rating_score = (avg_rating / 5) * 100
    
    growth_score = min(100, max(0, 50 + growth)) # Base 50, + growth %
    
    # Volume score based on order frequency (Simulated threshold)
    volume = len(orders)
    volume_score = min(100, (volume / 20) * 100) # Assuming 20 orders/month is a "good" benchmark
    
    performance_score = (rating_score * 0.3) + (growth_score * 0.3) + (volume_score * 0.4)
    
    # 4. Spike Detection
    # Using Z-score on daily transactions for the last 30 days
    is_spike = False
    daily_df = df.resample('D').agg({'revenue': 'sum'})
    if len(daily_df) > 5:
        mean = daily_df['revenue'].mean()
        std = daily_df['revenue'].std()
        if std > 0:
            last_day_rev = daily_df.iloc[-1]['revenue']
            z_score = (last_day_rev - mean) / std
            if z_score > 2:
                is_spike = True
    
    # 5. AI Insights & Recommendations
    insights = []
    recommendations = []
    
    if growth < -5:
        insights.append(f"Revenue dropped {abs(growth):.1f}% compared to last month.")
        recommendations.append("Offer a promotional discount on slow-moving items to boost volume.")
    elif growth > 5:
        insights.append(f"Impressive growth of {growth:.1f}% this month!")
        recommendations.append("Consider scaling up your ad spend to capitalize on this upward trend.")
    else:
        insights.append("Stable sales performance with consistent revenue.")
        recommendations.append("Focus on customer retention and personalized email marketing.")
        
    if avg_rating < 3.5:
        insights.append(f"Customer satisfaction is lower than average ({avg_rating:.1f} stars).")
        recommendations.append("Improve product packaging and ensure faster responses to customer queries.")
        
    if is_spike:
        insights.append("🔥 Unusual sales spike detected in the last 24 hours!")
        recommendations.append("Check for potential viral social media mentions or sudden demand shifts.")

    # Top selling products
    top_products = Product.objects.filter(seller=seller).annotate(
        total_sold=Sum('orderitem__quantity')
    ).filter(total_sold__gt=0).order_by('-total_sold')[:5]

    return {
        'seller_name': seller.display_name,
        'total_revenue': float(df['revenue'].sum()),
        'total_orders': len(orders),
        'avg_rating': round(avg_rating, 1),
        'performance_score': round(performance_score, 1),
        'growth': round(growth, 1),
        'predicted_revenue': round(prediction, 2),
        'insights': insights,
        'recommendations': recommendations,
        'monthly_labels': [d.strftime('%b %Y') for d in monthly_df.index],
        'monthly_data': [float(r) for r in monthly_df['revenue']],
        'monthly_orders': [int(c) for c in monthly_df['orders']],
        'top_products': [{'name': p.name, 'sold': p.total_sold} for p in top_products],
        'ai_date': timezone.now().strftime('%B %d, %Y'),
        'ai_prediction': f"₹{int(prediction):,}"
    }
