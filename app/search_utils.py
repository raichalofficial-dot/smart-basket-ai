import re
from rapidfuzz import process, fuzz
from .models import Product, Category

def smart_search_logic(query):
    query = query.lower().strip()
    products = Product.objects.all()
    
    # 1. Natural Language Intent Detection
    # Price detection: "under 50", "below 100", "under 500 rupees"
    price_match = re.search(r'(?:under|below|less than)\s*(\d+)', query)
    price_limit = int(price_match.group(1)) if price_match else None
    
    # Flags detection
    is_new_query = "new" in query
    is_best_selling = "best selling" in query or "popular" in query
    
    is_cheap = "cheap" in query or "low price" in query
    
    # Category detection
    categories = Category.objects.all()
    target_category = None
    for cat in categories:
        if cat.CategoryName.lower() in query:
            target_category = cat
            break

    # 2. Filter base queryset
    if target_category:
        products = products.filter(category=target_category)
    if price_limit:
        products = products.filter(price__lte=price_limit)
    if is_new_query:
        products = products.filter(is_new=True)

    if is_cheap:
        products = products.order_by('price')
    elif is_best_selling:
        products = products.order_by('-sales_count')

    # 3. Fuzzy Matching on Names (Spelling Tolerance)
    # If a specific product name is being searched with typos
    # We strip the "NL keywords" to get the core search term
    clean_query = query
    for word in ["under", "below", "rupees", "new", "best selling", "show me"]:
        clean_query = clean_query.replace(word, "")
    clean_query = clean_query.strip()

    product_names = [p.name for p in products]
    matches = process.extract(clean_query, product_names, scorer=fuzz.WRatio, limit=10)
    
    # Filter matches with a reasonable score (e.g., > 60)
    matched_names = [m[0] for m in matches if m[1] > 60]
    
    if matched_names:
        # Return matched products in order of similarity
        results = []
        for name in matched_names:
            results.extend(products.filter(name=name))
        return list(dict.fromkeys(results)) # Remove duplicates
    
    return list(products[:10]) # Fallback

def parse_voice_order(text):
    """
    Extracts quantity and product from text like "Add 2 Amul Cheese to cart"
    Returns (quantity, product_name)
    """
    text = text.lower()
    # Regex for "add 2 amul cheese" or "order 1 tata salt"
    match = re.search(r'(?:add|order|buy)\s*(\d+)\s*(?:kg|g|unit|units|piece|pieces)?\s+(.+)', text)
    if match:
        qty = int(match.group(1))
        p_name = match.group(2).replace("to cart", "").replace("to my cart", "").strip()
        return qty, p_name
    return None, None
