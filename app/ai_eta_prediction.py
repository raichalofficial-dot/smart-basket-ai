"""
AI ETA Prediction Module for SmartBasket Online
Uses Haversine distance + traffic estimation + order load
"""
import math
from datetime import datetime


def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance between two points using Haversine formula.
    Returns distance in kilometers.
    """
    R = 6371  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    return round(R * c, 2)


def estimate_traffic_delay(traffic_level="LOW"):
    """
    Estimate traffic delay in minutes.
    LOW    → 0 min
    MEDIUM → 10 min  
    HIGH   → 20 min
    """
    delays = {
        "LOW": 0,
        "MEDIUM": 10,
        "HIGH": 20,
    }
    return delays.get(traffic_level.upper(), 0)


def get_traffic_level_auto():
    """
    Automatically determine traffic level based on time of day.
    Peak hours (8-10 AM, 5-8 PM) → HIGH
    Moderate hours (12-2 PM) → MEDIUM
    Other times → LOW
    """
    hour = datetime.now().hour
    if hour in range(8, 10) or hour in range(17, 20):
        return "HIGH"
    elif hour in range(12, 14):
        return "MEDIUM"
    return "LOW"


def calculate_order_load_delay(active_orders_count):
    """
    Calculate delay due to agent having multiple orders.
    Each additional order adds ~5 minutes delay.
    """
    if active_orders_count <= 1:
        return 0
    return (active_orders_count - 1) * 5


def predict_eta(distance_km, traffic_level="LOW", active_orders=1):
    """
    AI ETA Prediction.
    Formula: ETA = (Distance / Avg Speed) * 60 + Traffic Delay + Order Load Delay
    
    Average speed: 30 km/h (city driving)
    
    Returns dict with distance, traffic info, and ETA in minutes.
    """
    avg_speed_kmh = 30
    
    # Base travel time
    travel_time_minutes = (distance_km / avg_speed_kmh) * 60
    
    # Traffic delay
    traffic_delay = estimate_traffic_delay(traffic_level)
    
    # Order load delay
    order_delay = calculate_order_load_delay(active_orders)
    
    # Total ETA
    total_eta = travel_time_minutes + traffic_delay + order_delay
    total_eta = max(5, round(total_eta))  # Minimum 5 minutes
    
    return {
        "distance_km": round(distance_km, 2),
        "traffic_level": traffic_level,
        "traffic_delay_mins": traffic_delay,
        "order_load_delay_mins": order_delay,
        "predicted_eta_mins": total_eta,
    }


def get_eta_display(distance_km, traffic_level="LOW", active_orders=1):
    """
    Helper that returns a simple ETA string for templates.
    """
    result = predict_eta(distance_km, traffic_level, active_orders)
    eta = result["predicted_eta_mins"]
    if eta < 60:
        return f"{eta} minutes"
    hours = eta // 60
    mins = eta % 60
    return f"{hours}h {mins}m"
