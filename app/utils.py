import math

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in KM
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))

    return R * c



import re
from decimal import Decimal

def parse_weight(weight_str):
    """
    Converts '5kg' or '100g' into (Decimal('5'), 'kg')
    """
    if not weight_str:
        return None, None

    match = re.match(r'^([\d.]+)\s*(kg|g|l|ml|mg)$', weight_str.lower())
    if not match:
        return None, None

    value = Decimal(match.group(1))
    unit = match.group(2)

    return value, unit

def normalize_quantity(value, unit):
    """
    Normalizes weight/volume to a base unit (g or ml) for comparison.
    """
    if not value or not unit:
        return None
    
    value = Decimal(str(value))
    unit = unit.lower()
    
    if unit == 'kg':
        return value * 1000, 'g'
    if unit == 'l':
        return value * 1000, 'ml'
    return value, unit
