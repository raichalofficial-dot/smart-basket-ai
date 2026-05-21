import pandas as pd
import numpy as np
from .models import Product, Category

def optimize_budget_cart(budget, plan_type, family_size=1, diet_pref="Mixed"):
    """
    AI Budget Optimization: Balanced grocery cart generation based on
    nutritional categories, family size, and diet preferences.
    """
    try:
        budget = float(budget)
        family_size = int(family_size)
    except (ValueError, TypeError):
        return {"recommended_items": [], "total_cost": 0, "remaining_budget": 0}
    
    # 1. Category-wise Budget Allocation (Percentage based)
    category_weights = {
        'Rice & Grains': 0.35,
        'Dairy': 0.20,
        'Protein': 0.15, 
        'Cooking Essentials': 0.15,
        'Snacks': 0.10,
        'Vegetables': 0.05
    }
    
    if diet_pref == "Veg":
        category_weights['Protein'] = 0.10
        category_weights['Vegetables'] = 0.10
    elif diet_pref == "Non-Veg":
        category_weights['Protein'] = 0.25
        category_weights['Rice & Grains'] = 0.30

    cat_mapping = {
        'Grocery & Staples': 'Rice & Grains',
        'milk products': 'Dairy',
        'Vegetables': 'Vegetables',
        'Fruits': 'Vegetables',
        'Cooking Essentials': 'Cooking Essentials',
        'Spices & Powders': 'Cooking Essentials',
        'Health & Nutrition': 'Snacks',
        'Meat': 'Protein',
        'Seafood': 'Protein',
        'Beverages': 'Snacks',
        'Snacks': 'Snacks',
        'Packaged & branded foods': 'Snacks',
        'Breakfast & Spread Items': 'Snacks',
        'Frozen & Ready-to-Cook Foods': 'Protein', 
    }

    products = Product.objects.all().select_related('category')
    
    if not products.exists():
        return {"recommended_items": [], "total_cost": 0, "remaining_budget": budget}

    # 2. Extract Data
    data = []
    for p in products:
        # Diet Preference Check
        if diet_pref == "Veg":
            if p.category.CategoryName in ['Meat', 'Seafood'] or \
               any(word in p.name.lower() for word in ['chicken', 'fish', 'meat', 'beef', 'pork']):
                continue

        # Get best price variant if quantity-based
        selling_price = float(p.price - (p.price * p.discount / 100))
        qty_label = "1 unit"
        
        if p.product_type == 'quantity':
            qp = p.quantity_prices.order_by('price').first()
            if qp:
                selling_price = float(qp.price)
                qty_label = qp.quantity
        
        data.append({
            'id': p.id,
            'name': p.name,
            'category_name': p.category.CategoryName,
            'price': selling_price,
            'qty_label': qty_label,
            'priority': p.priority_level or 'optional',
            'stock': p.stock if p.product_type == 'piece' else 50,
        })

    df = pd.DataFrame(data)
    if df.empty:
        return {"recommended_items": [], "total_cost": 0, "remaining_budget": budget}
    
    # 3. Allocation
    selected_items = []
    total_cost = 0
    actual_remaining = budget
    
    allocated_budgets = {k: v * budget for k, v in category_weights.items()}
    
    # Sort by priority and price
    df['priority_val'] = df['priority'].map({'essential': 0, 'standard': 1, 'optional': 2}).fillna(2)
    df = df.sort_values(by=['priority_val', 'price'])

    for group_name, group_budget in allocated_budgets.items():
        mapped_cats = [k for k, v in cat_mapping.items() if v == group_name]
        cat_products = df[df['category_name'].isin(mapped_cats)]
        
        category_spent = 0
        for _, row in cat_products.iterrows():
            if row['stock'] <= 0: continue
            
            qty = 1
            if group_name in ['Rice & Grains', 'Dairy', 'Vegetables', 'Protein']:
                if family_size > 4: qty = 2
            
            item_cost = row['price'] * qty
            
            if category_spent + item_cost <= group_budget and actual_remaining >= item_cost:
                selected_items.append({
                    'id': int(row['id']),
                    'name': row['name'],
                    'price': row['price'],
                    'qty': qty,
                    'qty_label': row['qty_label'],
                    'total': round(item_cost, 2),
                    'category': row['category_name']
                })
                category_spent += item_cost
                total_cost += item_cost
                actual_remaining -= item_cost
            
            if category_spent >= group_budget:
                break

    # Alternatives for savings
    alternatives = []
    for item in selected_items[:3]:
        cheaper = df[(df['category_name'] == item['category']) & (df['price'] < item['price'])].head(1)
        if not cheaper.empty:
            alt = cheaper.iloc[0]
            savings = (item['price'] - alt['price']) * item['qty']
            if savings > 2:
                alternatives.append({
                    'original_item': item['name'],
                    'alternative_item': alt['name'],
                    'savings': round(savings, 2)
                })

    return {
        "recommended_items": selected_items,
        "total_cost": round(total_cost, 2),
        "remaining_budget": round(actual_remaining, 2),
        "alternatives": alternatives
    }
