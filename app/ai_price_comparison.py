
import pandas as pd
from .models import Product, Vendor, VendorPrice
from django.db.models import Q

def get_vendor_prices(product_id):
    """
    Returns a list of vendor prices for a specific product.
    Now includes the current product and other sellers' products with the same name.
    """
    target_product = Product.objects.get(id=product_id)
    
    # 1. Get from VendorPrice (External Vendors)
    v_prices = VendorPrice.objects.filter(product_id=product_id).select_related('vendor')
    
    data = []
    for vp in v_prices:
        data.append({
            'source': 'External Vendor',
            'vendor_id': vp.vendor.id,
            'vendor_name': vp.vendor.vendor_name,
            'location': vp.vendor.location or "Online",
            'rating': vp.vendor.rating,
            'base_price': float(vp.price),
            'price': float(vp.price),  # Alias for backward compatibility
            'discount': float(vp.discount),
            'final_price': float(vp.final_price),
            'stock': vp.stock,
            'is_available': vp.stock > 0,
            'is_current': False
        })
    
    # 2. Get from Platform Sellers (Internal)
    # Search for products with the same name across all sellers
    platform_products = Product.objects.filter(
        name__iexact=target_product.name
    ).select_related('seller')
    
    for op in platform_products:
        final_p = op.price - (op.price * op.discount / 100)
        is_current = (op.id == target_product.id)
        
        # Check if it has quantity variants
        if op.product_type == 'quantity':
            qps = op.quantity_prices.all()
            for qp in qps:
                data.append({
                    'vendor_id': op.seller.id,
                    'vendor_name': f"{op.seller.display_name} ({qp.quantity})",
                    'source': 'Platform Seller',
                    'location': op.seller.city or "Local Shop",
                    'rating': 4.5, 
                    'base_price': float(qp.price),
                    'price': float(qp.price),
                    'discount': float(op.discount),
                    'final_price': float(qp.price - (qp.price * op.discount / 100)),
                    'stock': qp.stock,
                    'is_available': qp.stock > 0,
                    'is_current': is_current
                })
        else:
            data.append({
                'vendor_id': op.seller.id,
                'vendor_name': op.seller.display_name,
                'source': 'Platform Seller',
                'location': op.seller.city or "Local Shop",
                'rating': 4.5,
                'base_price': float(op.price),
                'price': float(op.price),
                'discount': float(op.discount),
                'final_price': float(final_p),
                'stock': op.stock or 0,
                'is_available': (op.stock or 0) > 0,
                'is_current': is_current
            })
    
    # Sort by final price ascending
    data.sort(key=lambda x: x['final_price'])
    return data

def find_best_price(product_id):
    """
    Detects the best deal among vendors.
    """
    prices = get_vendor_prices(product_id)
    if prices:
        return prices[0]
    return None

def get_discounted_products():
    """
    Finds top discounted products across all vendors.
    """
    discounts = VendorPrice.objects.filter(discount__gt=0).select_related('product', 'vendor').order_by('-discount')[:5]
    result = []
    for d in discounts:
        result.append({
            'product_name': d.product.name,
            'vendor_name': d.vendor.vendor_name,
            'original_price': float(d.price),
            'discount_percent': float(d.discount),
            'final_price': float(d.final_price)
        })
    return result

def suggest_cheaper_alternatives(product_id):
    """
    Suggests cheaper alternatives in the same category.
    Logic: Same category, cheaper price, similar rating (if available).
    """
    try:
        target_product = Product.objects.get(id=product_id)
        
        # Find products in same category that are cheaper
        alternatives = Product.objects.filter(
            category=target_product.category,
            price__lt=target_product.price
        ).exclude(id=product_id).order_by('price')[:3]
        
        alt_list = []
        for alt in alternatives:
            alt_list.append({
                'id': alt.id,
                'name': alt.name,
                'price': float(alt.price),
                'brand': alt.brand.brandName if alt.brand else "N/A"
            })
        
        return alt_list
    except Product.DoesNotExist:
        return []

# Helper for existing view logic (backward compatibility if needed)
def get_product_price_comparison(product_id):
    data = get_vendor_prices(product_id)
    if not data:
        return None
    return pd.DataFrame(data)

def get_best_deal(product_id):
    return find_best_price(product_id)

def get_alternative_products(product_id):
    return suggest_cheaper_alternatives(product_id)
