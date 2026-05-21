import re
from rapidfuzz import process, fuzz
from .models import Product, Order, Cart, CustomUser

def fuzzy_product_search(query):
    """
    Finds products using fuzzy matching for spelling correction.
    """
    query = query.lower().strip()
    all_products = Product.objects.all()
    product_names = [p.name for p in all_products]
    
    # Fuzzy match using WRatio (good for partials and typos)
    matches = process.extract(query, product_names, scorer=fuzz.WRatio, limit=10)
    
    # Score threshold of 60 for usability
    matched_names = [m[0] for m in matches if m[1] > 60]
    
    results = []
    if matched_names:
        for name in matched_names:
            results.extend(all_products.filter(name=name))
    
    # Remove duplicates while preserving order
    return list(dict.fromkeys(results))

def extract_keywords(query):
    """
    Analyzes natural language queries and extracts filters.
    """
    query = query.lower().strip()
    filters = {}
    
    # Price detection
    price_match = re.search(r'(?:under|below|less than)\s*(\d+)', query)
    if price_match:
        filters['price_limit'] = int(price_match.group(1))
        
    # Cheap/Cheap sorting
    if "cheap" in query or "low price" in query:
        filters['sort'] = "price_low_high"
        
    # Best selling
    if "best" in query or "popular" in query:
        filters['sort'] = "sales"

    return filters

def repeat_last_order(user_id):
    """
    Retrieves the last order for a user and adds items to cart.
    """
    try:
        user = CustomUser.objects.get(id=user_id)
        last_order = Order.objects.filter(user=user).order_by('-created_at').first()
        
        if not last_order:
            return {"status": "error", "message": "No previous orders found."}
            
        added_items = []
        for item in last_order.items.all():
            Cart.objects.get_or_create(
                user=user,
                product=item.product,
                defaults={'quantity': item.quantity, 'price': item.product.price}
            )
            added_items.append(item.product.name)
            
        return {"status": "success", "items": added_items}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def process_voice_command(command, user_id):
    """
    Main entry point for voice command processing.
    """
    command = command.lower().strip()
    
    # 1. Check for repeat order intent
    if any(word in command for word in ["repeat", "again", "previous", "last"]):
        return repeat_last_order(user_id)
        
    # 2. Check for add to cart intent
    # Matches "Add 2 Milk", "Add 1 Bread to cart", etc.
    match = re.search(r'(?:add|order|buy)\s*(\d+)?\s*(?:kg|g|unit|units|piece|pieces)?\s+(.+)', command)
    if match:
        qty = int(match.group(1)) if match.group(1) else 1
        p_name = match.group(2).replace("to cart", "").replace("to my cart", "").strip()
        
        # Fuzzy search the product
        matches = fuzzy_product_search(p_name)
        if matches:
            product = matches[0] # Take best match
            user = CustomUser.objects.get(id=user_id)
            Cart.objects.create(
                user=user,
                product=product,
                quantity=qty,
                price=product.price
            )
            return {"status": "success", "message": f"Added {qty} {product.name} to cart!", "type": "cart"}
            
    # 3. If no command intent, treat as a search
    return {"status": "search", "query": command}
