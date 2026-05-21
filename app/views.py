import random
import string
from decimal import Decimal

from django.contrib.auth import authenticate, logout, login as auth_login

import json
import requests
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db.models import Q
from .forms import *
from .models import *
from .utils import parse_weight, normalize_quantity
from .analytics import get_seller_performance, get_seller_intelligence_data, summarize_seller_intelligence
from .search_utils import smart_search_logic, parse_voice_order
from .delivery_ai import predict_delivery_eta
from django.db.models import Sum, Count, Avg, F, ExpressionWrapper, DecimalField
from django.db.models.functions import TruncDay, TruncMonth, TruncYear
from datetime import date
from django.db.models import Case, When, Value, IntegerField


def adminlogin(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_superuser:
                auth_login(request, user)
                request.session['user_id'] = user.id
                request.session['username'] = user.username
                request.session['user_type'] = 'admin'
                return redirect("admin_dashboard")
            else:
                messages.error(request, "You are not authorized as admin.")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "login.html")
def admin_dashboard(request):
    if request.session.get("user_type") != "admin":
        if not request.user.is_superuser:
            return redirect("adminlogin")

    pending_sellers = SellerProfiles.objects.filter(is_active=False)
    pending_partner=DeliveryPartnerProfile.objects.filter(is_active=False)



    complaints = Complaint.objects.all().annotate(
        priority_order=Case(
            When(priority='HIGH', then=Value(1)),
            When(priority='MEDIUM', then=Value(2)),
            When(priority='LOW', then=Value(3)),
            output_field=IntegerField(),
        )
    ).order_by('priority_order', '-created_at')



    total_sellers = SellerProfiles.objects.count()
    total_customers = CustomUser.objects.filter(user_type='customer').count()
    total_delivery_partners = DeliveryPartnerProfile.objects.count()
    total_products = Product.objects.count()
    total_orders = Order.objects.count()

    total_revenue = Order.objects.aggregate(total=Sum('total_amount'))['total'] or 0

    today = date.today()
    todays_deliveries = Delivery.objects.filter(order__created_at__date=today)
    total_deliveries_today = todays_deliveries.count()
    delivered_count = todays_deliveries.filter(status='DELIVERED').count()
    failed_count = 0
    pending_delivery_count = total_deliveries_today - delivered_count - failed_count

    return render(request,'admin/dashboard.html',{
        "pendingSellers":pending_sellers,
        'pending_partner':pending_partner,
        'complaints': complaints,
        'active_sellers': SellerProfiles.objects.filter(is_active=True),
        'total_sellers': total_sellers,
        'total_customers': total_customers,
        'total_delivery_partners': total_delivery_partners,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'total_deliveries_today': total_deliveries_today,
        'delivered_count': delivered_count,
        'pending_delivery_count': pending_delivery_count,
        'failed_count': failed_count,
        'all_partners': DeliveryAgent.objects.all(),
    })

def admin_manage_complaints(request):
    if request.session.get("user_type") != "admin":
        if not request.user.is_superuser:
            return redirect("adminlogin")

    priority_filter = request.GET.get('priority')
    status_filter = request.GET.get('status')
    order_id_search = request.GET.get('order_id')

    complaints = Complaint.objects.all()

    if priority_filter:
        complaints = complaints.filter(priority=priority_filter)
    if status_filter:
        complaints = complaints.filter(status=status_filter)
    if order_id_search:
        complaints = complaints.filter(order__id=order_id_search)

    from django.db.models import Case, When, Value, IntegerField
    complaints = complaints.annotate(
        priority_order=Case(
            When(priority='HIGH', then=Value(1)),
            When(priority='MEDIUM', then=Value(2)),
            When(priority='LOW', then=Value(3)),
            output_field=IntegerField(),
        )
    ).order_by('priority_order', '-created_at')

    return render(request, "admin/manage_complaints.html", {
        "complaints": complaints,
        "priority_filter": priority_filter,
        "status_filter": status_filter,
        "order_id_search": order_id_search
    })

@csrf_exempt
def approve_delivery(request, id):

    if request.method == "POST":

        partner = DeliveryPartnerProfile.objects.get(id=id)
        partner.is_active = True
        partner.save()
        print("************************8",partner.is_active)

        return JsonResponse({"success": True})

    return JsonResponse({"success": False})

from django.db.models import Sum

def commission_details(request):

    orders = Order.objects.filter(status="delivered")

    total_sales = orders.aggregate(total=Sum('total_amount'))['total'] or 0
    total_commission = orders.aggregate(total=Sum('commission_amount'))['total'] or 0
    print("************************ :",total_sales,total_commission,orders)

    context = {
        "orders": orders,
        "total_sales": total_sales,
        "total_commission": total_commission
    }

    return render(request, "admin/commission_details.html", context)
def admin_seller_analysis(request):
    sellers = SellerProfiles.objects.filter(is_active=True)
    return render(request, 'admin/seller_analysis_list.html', {'sellers': sellers})

def admin_seller_report(request, seller_id):
    from .ai_analysis import analyze_seller_ai
    report_data = analyze_seller_ai(seller_id)
    return render(request, 'admin/seller_report.html', {'report': report_data, 'seller_id': seller_id})

def submit_complaint(request):
    if request.session.get("user_type") != "customer":
        return redirect("login", role="customer")

    customer = CustomUser.objects.get(id=request.session.get("user_id"))
    orders = Order.objects.filter(user=customer)

    if request.method == "POST":
        order_id = request.POST.get("order")
        title = request.POST.get("title", "No Title")
        text = request.POST.get("text")

        order = None
        if order_id:
            order = Order.objects.get(id=order_id)

        Complaint.objects.create(
            customer=customer,
            order=order,
            title=title,
            text=text
        )
        messages.success(request, "Your complaint has been submitted and prioritized.")
        return redirect("customer_complaints")

    return render(request, "customer/submit_complaint.html", {"orders": orders})

def customer_complaints(request):
    if request.session.get("user_type") != "customer":
        return redirect("login", role="customer")

    customer = CustomUser.objects.get(id=request.session.get("user_id"))
    complaints = Complaint.objects.filter(customer=customer).order_by('-created_at')
    return render(request, "customer/my_complaints.html", {"complaints": complaints})

def seller_complaints(request):
    if request.session.get("user_type") != "seller":
        return redirect("login", role="seller")

    seller = sellerindex(request)
    complaints = Complaint.objects.filter(order__items__product__seller=seller).distinct().order_by('-created_at')

    return render(request, "seller/complaints.html", {"complaints": complaints})
@csrf_exempt
def approve_seller(request, id):
    if request.method == 'POST':
        seller = get_object_or_404(SellerProfiles, id=id)
        seller.is_active = True
        seller.save()
        return redirect("admin_dashboard")

def update_complaint_status(request, complaint_id, status):
    if request.session.get("user_type") != "admin":
        if not request.user.is_superuser:
            return redirect("adminlogin")

    complaint = get_object_or_404(Complaint, id=complaint_id)
    complaint.status = status
    complaint.save()
    messages.success(request, f"Complaint added")
    return redirect("admin_dashboard")

def index(request):
    return render(request,"index.html")

def logout_view(request):
    logout(request)
    return redirect('index')


def register(request,role):
    role=role
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.user_type = role
            user.save()
            messages.success(request, "Registration successful. You can now log in.")
            return redirect('login',role)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    field_name = form.fields[field].label or field if field != '__all__' else ''
                    messages.error(request, f"{field_name}: {error}" if field_name else error)
            return redirect('register', role)
    else:
        form = RegistrationForm()
    return render(request, 'register.html', {'form': form,"role":role})

def login(request,role):
    role=role
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None and user.user_type==role:
            auth_login(request, user)

            request.session['user_id'] = user.id
            request.session['user_type'] = role
            request.session['username'] = user.username
            request.session['email'] = user.email
            request.session['user_type'] = user.user_type

            if user.user_type == "seller":
                return redirect("seller_index")
            elif user.user_type == "customer" :
                return redirect("customer_index")
            else:
                return redirect("delivery_index")
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "login.html",{"role":role})

def seller_index(request):
    print("*************loggined user : ",request.user)

    if request.session.get("user_type") != "seller":
        return redirect("login", role="seller")

    seller_id = request.session.get("user_id")
    seller=CustomUser.objects.get(id=seller_id)

    seller_profile = None
    important_insights = []
    metrics = None
    deliveries = []
    total_products = 0
    average_rating = 0.0
    seller_profile = None
    has_profile = False

    try:
        seller_profile = SellerProfiles.objects.get(seller=seller)
        has_profile = True
    except SellerProfiles.DoesNotExist:
        has_profile = False

    today = timezone.localdate()
    now = timezone.now()

    if has_profile:
        metrics = get_seller_intelligence_data(seller_profile)
        deliveries = Delivery.objects.filter(
            order__items__product__seller=seller_profile,
            status__in=['PACKED', 'DISPATCHED', 'NEARBY']
        ).distinct().order_by('-id')

        from django.db.models import Avg
        from .ai_restock_assistant import get_restock_insights

        products = Product.objects.filter(seller=seller_profile)
        total_products = products.count()
        avg_rtg = Review.objects.filter(product__seller=seller_profile).aggregate(Avg('rating'))['rating__avg']
        if avg_rtg:
            average_rating = round(avg_rtg, 1)

        restock_data = get_restock_insights(seller_profile)
        restock_insights = restock_data.get('insights', [])
        important_insights = [i for i in restock_insights if i['priority'] != 'Low' or i['performance'] == 'Fast Selling'][:5]

    profit_margin = 0
    if has_profile and metrics and metrics.get('total_revenue', 0) > 0:
        profit_margin = 95

    return render(request, "seller/sellerindex.html", {
        "has_profile": has_profile,
        "seller": seller_profile,
        "metrics": metrics,
        "deliveries": deliveries,
        "total_products": total_products,
        "average_rating": average_rating,
        "restock_insights": important_insights,
        "profit_margin": profit_margin
    })


@csrf_exempt
def reverse_geocode(request):
    if request.method == "POST":
        data = json.loads(request.body)

        lat = data.get("latitude")
        lon = data.get("longitude")

        if not lat or not lon:
            return JsonResponse({"error": "Latitude and longitude are required"}, status=400)

        try:
            lat = float(lat)
            lon = float(lon)
        except ValueError:
            return JsonResponse({"error": "Invalid latitude or longitude"}, status=400)

        url = "https://api.bigdatacloud.net/data/reverse-geocode-client"
        params = {
            "latitude": lat,
            "longitude": lon,
            "localityLanguage": "en"
        }

        response = requests.get(url, params=params)

        if response.status_code != 200:
            return JsonResponse({"error": f"Geocoding service error: {response.status_code}. Please wait 5 seconds and try again."}, status=500)

        try:
            result = response.json()
        except requests.exceptions.JSONDecodeError:
            return JsonResponse({"error": "Invalid response from geocoding service"}, status=500)

        admin_list = result.get("localityInfo", {}).get("administrative", [])

        city_variants = []
        for admin in admin_list:
             if 'name' in admin:
                  city_variants.append(admin['name'])


        city = result.get("city") or result.get("locality") or result.get("principalSubdivision") or "Unknown City"
        locality = result.get("locality", "")
        subdivision = result.get("principalSubdivision", "")
        country = result.get("countryName", "India")

        display_city = locality if locality and locality != city else city

        address_parts = []
        for part in [locality, city, subdivision, country]:
             if part and part not in address_parts:
                  address_parts.append(part)

        display_address = ", ".join(address_parts)

        return JsonResponse({
            "address": display_address,
            "city": display_city,
            "latitude": lat,
            "longitude": lon
        })

    return JsonResponse({"error": "Invalid request"}, status=400)
def create_seller_profile(request):
    userid=request.session.get('user_id')
    user=CustomUser.objects.get(id=userid)
    if user.user_type != 'seller':
        messages.error(request, "Access denied.")
        return redirect('login')

    if SellerProfiles.objects.filter(seller=user).exists():
        return redirect('seller_profile_display')
    seller_id = request.session.get("user_id")
    seller = CustomUser.objects.get(id=seller_id)

    if request.method == 'POST':
        address = request.POST.get('address')
        if not address:
            messages.warning(request, "Please provide an address (use the location button).")
            return redirect('create_seller_profile')

        SellerProfiles.objects.create(
            seller=seller,
            display_name=request.POST.get('display_name'),
            city=request.POST.get('city'),
            document = request.FILES.get('document'),
            address=request.POST.get('address'),
            latitude=request.POST.get('latitude'),
            longitude=request.POST.get('longitude'),
            opening_time=request.POST.get('opening_time'),
            closing_time=request.POST.get('closing_time'),
        )

        messages.success(request, "Seller profile created successfully!")
        return redirect('seller_index')

    return render(request, 'seller/create_profile.html')
def seller_profile_display(request):

    if request.session.get("user_type") != "seller":
        return redirect("login", role="seller")

    user_id = request.session.get("user_id")

    try:
        profile = SellerProfiles.objects.get(seller_id=user_id)
    except SellerProfiles.DoesNotExist:
        messages.warning(request, "Please create your seller profile first.")
        return redirect("create_seller_profile")

    return render(request, "seller/seller_profile.html", {
        "profile": profile
    })


def sellerindex(request):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    try:
        from .models import CustomUser, SellerProfiles
        user = CustomUser.objects.get(id=user_id)
        return SellerProfiles.objects.get(seller=user)
    except (CustomUser.DoesNotExist, SellerProfiles.DoesNotExist):
        return None
def manage_category(request):
    seller = sellerindex(request)
    if not seller:
        messages.warning(request, "Please create your seller profile first.")
        return redirect("create_seller_profile")

    if request.method == "POST":
        name = request.POST.get("category_name")
        if name:
            Category.objects.create(
                seller=seller,
                CategoryName=name
            )
        return redirect('manage_category')

    categories = Category.objects.filter(seller=seller)

    return render(request, "seller/manage_category.html", {
        "categories": categories
    })


def delete_category(request, cat_id):
    seller = sellerindex(request)
    if not seller: return redirect("create_seller_profile")
    category = get_object_or_404(Category, id=cat_id, seller=seller)
    category.delete()
    return redirect('manage_category')

def manage_brands(request):
    seller = sellerindex(request)
    if not seller:
        messages.warning(request, "Please create your seller profile first.")
        return redirect("create_seller_profile")

    if request.method == "POST":
        brand_name = request.POST.get("brand_name")
        category_id = request.POST.get("category")

        if brand_name and category_id:
            category = get_object_or_404(Category, id=category_id, seller=seller)

            Brands.objects.create(
                seller=seller,
                category=category,
                brandName=brand_name
            )
        return redirect('manage_brands')

    categories = Category.objects.filter(seller=seller)
    brands = Brands.objects.filter(seller=seller).select_related('category')

    return render(request, "seller/manage_brands.html", {
        "categories": categories,
        "brands": brands
    })

def delete_brand(request, brand_id):
    seller = sellerindex(request)
    if not seller: return redirect("create_seller_profile")
    brand = get_object_or_404(Brands, id=brand_id, seller=seller)
    brand.delete()
    return redirect('manage_brands')
def add_product(request):
    seller = sellerindex(request)
    if not seller:
        messages.warning(request, "Please create your seller profile first.")
        return redirect("create_seller_profile")

    products = Product.objects.filter(seller=seller).select_related('category', 'brand')

    if request.method == "POST":
        form = ProductForm(request.POST)

        product_type = request.POST.get("product_type")

        if form.is_valid():
            product = form.save(commit=False)
            product.seller = seller
            product.product_type = product_type

            if product_type == "piece":
                product.stock = request.POST.get("stock")

            product.save()

            images = request.FILES.getlist('image')
            for img in images:
                ProductImage.objects.create(product=product, image=img)

            if product_type == 'quantity':
                quantities = request.POST.getlist('quantity')
                prices = request.POST.getlist('qprice')
                stocks = request.POST.getlist('qstock')

                for q, p, s in zip(quantities, prices, stocks):
                    if q and p and s:
                        ProductQuantityPrice.objects.create(
                            product=product,
                            quantity=q,
                            price=p,
                            stock=s
                        )

            return redirect('manage_products')

    else:
        form = ProductForm()

    return render(request, 'seller/manage_products.html', {
        'form': form,
        'products': products
    })


def delete_product(request, product_id):
    seller = sellerindex(request)
    if not seller: return redirect("create_seller_profile")
    product = get_object_or_404(Product, id=product_id, seller=seller)
    product.delete()
    return redirect('manage_products')

def product_performance(request):
    if request.session.get("user_type") != "seller":
        return redirect("login", role="seller")

    seller = sellerindex(request)
    if not seller: return redirect("create_seller_profile")
    performance_results = get_seller_performance(seller)

    critical_items = [item['product'].name for item in performance_results if item['restock_alert']]
    if critical_items:
        messages.warning(request, f"Critical Restock Required: {', '.join(critical_items)}")

    fast_count = sum(1 for item in performance_results if "Fast" in item['status'])
    slow_count = sum(1 for item in performance_results if "Slow" in item['status'])
    moderate_count = len(performance_results) - fast_count - slow_count

    sales_by_day = {}
    for item in performance_results:
        for history in item['sales_history']:
            day = history['day'].strftime('%Y-%m-%d')
            sales_by_day[day] = sales_by_day.get(day, 0) + history['qty']

    sorted_days = sorted(sales_by_day.keys())
    chart_data = {
        'fast': fast_count,
        'moderate': moderate_count,
        'slow': slow_count,
        'labels': sorted_days,
        'sales': [sales_by_day[day] for day in sorted_days]
    }

    return render(request, "seller/product_performance.html", {
        "performance_results": performance_results,
        "chart_data": json.dumps(chart_data)
    })

def seller_intelligence(request):
    if request.session.get("user_type") != "seller":
        return redirect("login", role="seller")

    seller = sellerindex(request)
    if not seller: return redirect("create_seller_profile")

    data = get_seller_intelligence_data(seller)
    performance = get_seller_performance(seller)

    commission_rate = 0.05
    commission_amount = data['total_revenue'] * commission_rate
    net_payout = data['total_revenue'] - commission_amount

    data.update({
        'commission_amount': round(commission_amount, 2),
        'net_payout': round(net_payout, 2)
    })

    from .models import Delivery
    deliveries = Delivery.objects.filter(
        order__items__product__seller=seller
    ).select_related('order').distinct().order_by('-id')[:10]

    return render(request, "seller/intelligence.html", {
        "metrics": data,
        "performance": performance,
        "deliveries": deliveries,
        "metrics_json": json.dumps(data)
    })

@require_POST
def apply_seller_discount(request):
    if request.session.get("user_type") != "seller":
        return JsonResponse({'status': 'error', 'message': 'Unauthorized access.'}, status=403)

    seller = sellerindex(request)
    if not seller:
        return JsonResponse({'status': 'error', 'message': 'Seller profile not found.'}, status=403)

    product_id = request.POST.get('product_id')
    if not product_id:
        return JsonResponse({'status': 'error', 'message': 'Missing product ID.'}, status=400)

    try:
        product = Product.objects.get(id=product_id, seller=seller)
    except Product.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Product not found.'}, status=404)

    product.discount = Decimal('10.0')
    product.save()

    return JsonResponse({
        'status': 'success',
        'message': 'Discount applied successfully.',
        'product_id': product.id,
        'discount': float(product.discount)
    })

def select_delivery_slot(request,total):
    if request.session.get("user_type") != "customer":
        return redirect("login", role="customer")

    from datetime import date
    slots = DeliverySlot.objects.filter(date=date.today(), current_orders__lt=10)

    if not slots.exists():
        for time_s, label in DeliverySlot.SLOT_TIME:
            DeliverySlot.objects.get_or_create(time_slot=time_s, date=date.today())
        slots = DeliverySlot.objects.filter(date=date.today())

    for s in slots:
        s.display_text = f"{s.current_orders}/{s.max_orders} Orders Filled"
        s.time_display = s.time_slot
        s.date_display = s.date.strftime("%B %d, %Y")

    if request.method == "POST":
        slot_id = request.POST.get("slot_id")
        slot = DeliverySlot.objects.get(id=slot_id)

        request.session['selected_slot_id'] = slot_id
        return redirect('checkout' ,total)

    pending_orders_count = Order.objects.filter(status='ordered').count()

    return render(request, "customer/delivery_selection.html", {
        "slots": slots,
        "pending_orders": pending_orders_count,
        "total":total
    })

@csrf_exempt
def predict_eta_api(request):
    """
    API endpoint for AI-powered ETA prediction
    """
    import json
    from .delivery_ai import predict_delivery_eta

    data = json.loads(request.body)
    distance = data.get('distance', 5.0)
    traffic = data.get('traffic', 'LOW')

    agents_avail = DeliveryAgent.objects.filter(is_available=True).count()
    if agents_avail == 0: agents_avail = 5

    pending_orders = Order.objects.filter(status='ordered').count()

    eta = predict_delivery_eta(distance, traffic, pending_orders, agents_avail)

    return JsonResponse({
        'eta': eta,
        'traffic_level': traffic,
        'distance': distance
    })

def track_delivery(request, order_id):
    return track_delivery_live(request, order_id)

def update_delivery_status(request, delivery_id, status):
    if request.session.get("user_type") != "seller" and not request.user.is_superuser:
        return redirect("login", role="seller")

    delivery = get_object_or_404(Delivery, id=delivery_id)
    delivery.status = status
    delivery.save()

    status_msg = {
        'PACKED': 'Your order has been packed and is ready for dispatch.',
        'DISPATCHED': 'Great news! Your order is out for delivery.',
        'NEARBY': 'The delivery agent is nearby! Please be ready to receive your order.',
        'DELIVERED': 'Success! Your order has been delivered. Enjoy your SmartBasket!'
    }

    Notification.objects.create(
        user=delivery.order.user,
        title=f"Order",
        message=status_msg.get(status, f"Your order status is now {status}")
    )

    DeliveryTracking.objects.create(
        delivery=delivery,
        status=status,
        lat=delivery.agent.latitude if delivery.agent and delivery.agent.latitude else 12.9716,
        lng=delivery.agent.longitude if delivery.agent and delivery.agent.longitude else 77.5946
    )

    messages.success(request, f"Delivery for Order")
    return redirect("seller_index")

def api_delivery_status(request, order_id):
    delivery = get_object_or_404(Delivery, order_id=order_id)
    logs = DeliveryTracking.objects.filter(delivery=delivery).order_by('-timestamp')

    log_data = []
    for log in logs:
        log_data.append({
            "status": log.status,
            "time": log.timestamp.strftime("%H:%M %p, %b %d")
        })

    return JsonResponse({
        "status": delivery.status,
        "eta": delivery.predicted_eta,
        "agent": delivery.agent.name if delivery.agent else "Assigning...",
        "logs": log_data
    })

def summarize_performance(request):
    if request.session.get("user_type") != "seller":
        return JsonResponse({"status": "error", "message": "Unauthorized"})

    seller = sellerindex(request)
    if not seller:
        return JsonResponse({"status": "error", "message": "Profile not found"})

    metrics = get_seller_intelligence_data(seller)
    performance = get_seller_performance(seller)

    summary = summarize_seller_intelligence(metrics, performance)
    return JsonResponse({"status": "success", "summary": summary})

@csrf_exempt
def seller_ai_chat(request):
    if request.session.get("user_type") != "seller":
        return JsonResponse({"status": "error", "message": "Unauthorized"})

    data = json.loads(request.body)
    user_query = data.get("message", "").lower()

    seller = sellerindex(request)
    if not seller:
        return JsonResponse({
            "status": "success",
            "response": "I see you haven't completed your seller profile yet. Please set it up in 'Profile Settings' so I can analyze your sales data!"
        })

    metrics = get_seller_intelligence_data(seller)
    performance = get_seller_performance(seller)

    if "sale" in user_query or "revenue" in user_query or "income" in user_query:
        response = f"Your total revenue for this month is ₹{metrics['total_revenue']:.2f}. You've received {metrics['today_orders']} orders today."
    elif "stock" in user_query or "inventory" in user_query:
        low_items = [p['product'].name for p in performance if p['restock_alert']]
        if low_items:
            response = f"You have {len(low_items)} items low on stock: {', '.join(low_items[:3])}. We recommend restocking immediately."
        else:
            response = "Your inventory looks healthy! All items have sufficient stock for now."
    elif "restock" in user_query or "order more" in user_query:
        total_needed = sum(p['recommended_restock'] for p in performance)
        response = f"Based on AI demand forecasting, we recommend you restock a total of {total_needed} units across your products to meet projected demand."
    elif "performance" in user_query or "best" in user_query:
        fast_moving = [p['product'].name for p in performance if "Fast" in p['status']]
        if fast_moving:
            response = f"Your best performing product is '{fast_moving[0]}'. It is moving very fast compared to others."
        else:
            response = "Your products are performing steadily. Keep an eye on the Dashboard for any sudden changes."
    else:
        response = "I'm your AI Business Assistant. You can ask me about your 'sales', 'stock alerts', 'restock advice', or 'product performance'."

    return JsonResponse({"status": "success", "response": response})







def create_customer_profile(request):

    user_id = request.session.get("user_id")
    role = request.session.get("role")

    if not user_id:
        return redirect("login",role)

    user = CustomUser.objects.get(id=user_id)

    profile = CustomerProfile.objects.filter(user=user).first()

    if profile:
        return render(request, "customer/view_profile.html", {"profile": profile})

    if request.method == "POST":

        full_name = request.POST.get("full_name")
        phone = request.POST.get("phone")
        address = request.POST.get("address")
        city = request.POST.get("city")
        latitude = request.POST.get("latitude")
        longitude = request.POST.get("longitude")

        if not phone or not phone.isdigit() or len(phone) != 10:
            messages.error(request, "Phone number must be exactly 10 digits.")
            return render(request, "customer/create_profile.html")

        if not latitude or not longitude:
            messages.error(request, "Latitude and longitude are required")
            return render(request, "customer/create_profile.html")

        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except ValueError:
            messages.error(request, "Invalid latitude or longitude values")
            return render(request, "customer/create_profile.html")

        CustomerProfile.objects.create(
            user=user,
            full_name=full_name,
            phone=phone,
            address=address,
            city=city,
            latitude=latitude,
            longitude=longitude
        )

        messages.success(request, "Profile Created Successfully")

        return redirect("customer_index")

    return render(request, "customer/create_profile.html")

from math import radians, sin, cos, sqrt, atan2
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371

    lat1 = radians(lat1)
    lon1 = radians(lon1)
    lat2 = radians(lat2)
    lon2 = radians(lon2)

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))

    return R * c

def customer_index(request):

    user_id = request.session.get("user_id")

    customer = CustomerProfile.objects.filter(user__id=user_id).first()

    if not customer:
        return redirect("create_customer_profile")

    customer_lat = customer.latitude
    customer_lon = customer.longitude

    sellers = SellerProfiles.objects.filter(is_active=True)

    nearby_sellers = []

    for seller in sellers:
        if seller.latitude and seller.longitude:

            distance = calculate_distance(
                customer_lat,
                customer_lon,
                seller.latitude,
                seller.longitude
            )

            if distance <= 10:
                nearby_sellers.append(seller.id)

    products = Product.objects.filter(seller__id__in=nearby_sellers)

    query = request.GET.get('q', '').strip()
    cart_count = Cart.objects.filter(user__id=user_id).count()
    if query:
        products = products.filter(
            Q(brand__brandName__icontains=query) |
            Q(category__CategoryName__icontains=query) |
            Q(short_description__icontains=query)
        )

        return render(request, 'customer/product_list.html', {
            'products': product_data(products),
            'cart_count': cart_count
        })

    featured_products = products.filter(is_featured=True)
    new_products = products.filter(is_new=True)

    context = {
        'featured_products': product_data(featured_products),
        'new_products': product_data(new_products),
        'user': request.session.get("username"),
        'cart_count': cart_count
    }

    return render(request, 'customer/customerindex.html', context)


def product_data(products_qs):
        data = []
        for p in products_qs:
            first_image = p.images.first()
            image_url = first_image.image.url if first_image else None
            selling_price = p.price - (p.price * p.discount / 100)
            avg_rtg = p.reviews.aggregate(Avg('rating'))['rating__avg'] or 0.0
            data.append({
                'id': p.id,
                'name': p.name,
                'short_description': p.short_description,
                'price': p.price,
                'discount': p.discount,
                'selling_price': selling_price,
                'image_url': image_url,
                'brand_name': p.brand.brandName,
                'seller_name': p.seller.display_name if p.seller else "Unknown Seller",
                'stock': p.stock,
                'product_type': p.product_type,
                'avg_rating': round(float(avg_rtg), 1),
                'review_count': p.reviews.count(),
            })
        return data

def product_detail(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    images = product.images.all()
    reviews = product.reviews.select_related('user').order_by('-created_at')

    if request.session.get("user_id"):
        try:
            user = CustomUser.objects.get(id=request.session.get("user_id"))
            BrowsingHistory.objects.create(user=user, product=product)
        except CustomUser.DoesNotExist:
            pass

    quantity_prices = None
    selling_price = None

    if product.product_type == 'quantity':
        quantity_prices = product.quantity_prices.all()
    else:
        selling_price = product.price - (product.price * product.discount / 100)

    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0.0
    avg_rating = round(float(avg_rating), 1)

    total_reviews = reviews.count()
    rating_breakdown = {}

    for i in range(5, 0, -1):
        count = reviews.filter(rating=i).count()
        percentage = (count / total_reviews * 100) if total_reviews > 0 else 0
        rating_breakdown[i] = {
            'count': count,
            'percentage': round(percentage, 1)
        }

    existing_review = None
    can_review = False
    if request.session.get("user_id"):
        try:
            user = CustomUser.objects.get(id=request.session.get("user_id"))
            existing_review = Review.objects.filter(user=user, product=product).first()

            can_review = Order.objects.filter(
                user=user,
                status__iexact="Delivered",
                items__product=product
            ).exists()
        except CustomUser.DoesNotExist:
            pass

    return render(request, 'customer/product_detail.html', {
        'product': product,
        'images': images,
        'selling_price': selling_price,
        'quantity_prices': quantity_prices,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'rating_breakdown': rating_breakdown,
        'can_review': can_review,
        'existing_review': existing_review,
    })

def product_list(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.all()

    if query:
        products = products.filter(
            Q(brand__brandName__icontains=query) |
            Q(category__CategoryName__icontains=query)|
            Q(short_description__icontains=query) |
            Q(name__icontains=query)
        )

    sort_by = request.GET.get('sort')
    if sort_by == "price_low_high":
        products = products.order_by("price")
    elif sort_by == "price_high_low":
        products = products.order_by("-price")
    elif sort_by == "newest":
        products = products.order_by("-id")
    context = {
        'products': product_data(products),
    }
    return render(request, 'customer/product_list.html', context)

from django.contrib import messages


from decimal import Decimal

from decimal import Decimal

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    user = CustomUser.objects.get(id=request.session.get("user_id"))

    price = request.POST.get('price')
    size = request.POST.get('size')
    weight_str = request.POST.get('weight')

    if not price:
        messages.error(request, "Please select a valid option.")
        return redirect('product_detail', product_id=product.id)

    price = Decimal(price)

    weight = weight_unit = None
    if product.product_type == 'quantity':
        if not weight_str:
            messages.error(request, "Please select weight.")
            return redirect('product_detail', product_id=product.id)
        weight, weight_unit = parse_weight(weight_str)

    cart_item = Cart.objects.filter(
        user=user,
        product=product,
        price=price,
        size=size,
        weight=weight,
        weight_unit=weight_unit
    ).first()

    if cart_item:
        cart_item.quantity += 1
        cart_item.save()
        messages.info(request, "Quantity updated in cart.")
    else:
        Cart.objects.create(
            user=user,
            product=product,
            price=price,
            size=size,
            weight=weight,
            weight_unit=weight_unit,
            quantity=1
        )
        messages.success(request, "Added to cart.")

    return redirect('product_detail', product_id=product.id)





def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    user = CustomUser.objects.get(id=request.session.get("user_id"))
    _, created = Wishlist.objects.get_or_create(user=user, product=product)
    if created:
        messages.success(request, f"{product.name} added to your wishlist.")
    else:
        messages.info(request, f"{product.name} is already in your wishlist.")
    return redirect('product_detail', product_id=product.id)


from .models import Wishlist

def view_wishlist(request):
    user=CustomUser.objects.get(id=request.session.get("user_id"))
    wishlist_items = Wishlist.objects.filter(user=user).select_related('product', 'product__brand', 'product__category')

    products = []
    for item in wishlist_items:
        product = item.product
        image = product.images.first()
        products.append({
            'id': product.id,
            'name': product.name,
            'short_description': product.short_description,
            'price': product.price,
            'discount': product.discount,
            'selling_price': product.price * (1 - product.discount / 100),
            'brand_name': product.brand.brandName,
            'image_url': image.image.url if image else None,
        })

    return render(request, 'customer/product_list.html', {
        'products': products,
        'page_title': 'My Wishlist',
        'wishlist_view': True
    })


from collections import defaultdict
from decimal import Decimal

from collections import defaultdict
from decimal import Decimal

def view_cart(request):
    user = CustomUser.objects.get(id=request.session.get("user_id"))

    group = FamilyGroup.objects.filter(members=user).first() or FamilyGroup.objects.filter(admin=user).first()
    if group:
        cart_items = Cart.objects.filter(user__in=group.members.all()).select_related(
            'product', 'product__brand', 'user'
        )
    else:
        cart_items = Cart.objects.filter(user=user).select_related(
            'product', 'product__brand'
        )

    grouped = defaultdict(lambda: {
        'quantity': 0,
        'total_price': Decimal('0.00'),
        'item': None,
        'added_by': set()
    })

    for item in cart_items:
        if item.price is None:
            fallback_price = Decimal(item.product.price)
            item.price = fallback_price
            item.save(update_fields=['price'])
        else:
            fallback_price = item.price

        key = (
            item.product.id,
            fallback_price,
            item.size,
            item.weight,
            item.weight_unit
        )

        grouped[key]['quantity'] += item.quantity
        grouped[key]['total_price'] += fallback_price * item.quantity
        grouped[key]['item'] = item
        if group and item.user != user:
            grouped[key]['added_by'].add(item.user.username)

    cart_products = []
    cart_total = Decimal('0.00')

    for data in grouped.values():
        item = data['item']
        image = item.product.images.first()

        cart_products.append({
            'cart_id': item.id,
            'product_id': item.product.id,
            'name': item.product.name,
            'brand': item.product.brand.brandName if item.product.brand else '',
            'selling_price': round(item.price, 2),
            'quantity': data['quantity'],
            'total_price': round(data['total_price'], 2),
            'weight': f"{item.weight}{item.weight_unit}" if item.weight else '',
            'size': item.size or '',
            'image_url': image.image.url if image else None,
            'added_by': ", ".join(data['added_by']) if data['added_by'] else None
        })

        cart_total += data['total_price']

    return render(request, 'customer/cart.html', {
        'cart_items': cart_products,
        'cart_total': round(cart_total, 2),
        'group': group
    })







def remove_from_cart(request, product_id):
    user_id = request.session.get("user_id")
    Cart.objects.filter(user_id=user_id, id=product_id).delete()
    messages.success(request, "Removed from cart.")
    return redirect('view_cart')

def update_cart_quantity(request, cart_id, action):
    user_id = request.session.get("user_id")
    cart_item = Cart.objects.filter(user_id=user_id, id=cart_id).first()

    if cart_item:
        if action == 'plus':
            cart_item.quantity += 1
        elif action == 'minus' and cart_item.quantity > 1:
            cart_item.quantity -= 1
        cart_item.save()

    return JsonResponse({'status': 'success'})




from decimal import Decimal
from django.db import transaction
from django.contrib import messages
from django.shortcuts import redirect, render, get_object_or_404
from .ai_restock_assistant import get_restock_insights
import json
def checkout(request, total):
    user = get_object_or_404(CustomUser, id=request.session.get("user_id"))
    cart_items = Cart.objects.filter(user=user).select_related('product')

    if not request.session.get('selected_slot_id'):
        messages.warning(request, "Please select an AI-predicted delivery slot before checkout.")
        return redirect('select_delivery_slot', total=total)

    if not cart_items.exists():
        messages.error(request, "Your cart is empty")
        return redirect('view_cart')

    cart_total = Decimal('0.00')
    for item in cart_items:
        cart_total += item.price * item.quantity

    # Budget Validation
    try:
        url_budget = Decimal(str(total))
        if cart_total > url_budget:
            messages.error(request, f"Total ₹{cart_total} exceeds your set budget of ₹{url_budget}. Please adjust your cart.")
            return redirect('view_cart')
    except (ValueError, TypeError, Decimal.InvalidOperation):
        pass # If total is not a valid number, skip budget check

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            address = request.POST.get("address")
            city = request.POST.get("city")
            postal_code = request.POST.get("postal_code")
            
            try:
                with transaction.atomic():
                    order = form.save(commit=False)
                    order.user = user
                    order.total_amount = cart_total
                    order.otp = random.randint(100000, 999999)
                    order.commission_amount = float(order.total_amount) * (10 / 100)
                    order.save()
                    request.session["order_id"] = order.id

                    slot_id = request.session.get('selected_slot_id')
                    try:
                        slot = DeliverySlot.objects.get(id=slot_id) if slot_id else None
                        agents_avail = DeliveryPartnerProfile.objects.filter(is_available=True).count() or 5
                        pending_orders = Order.objects.filter(status='ordered').count()

                        eta = predict_delivery_eta(4.5, 'LOW', pending_orders, agents_avail)

                        Delivery.objects.create(
                            order=order,
                            slot=slot,
                            agent=DeliveryPartnerProfile.objects.filter(is_available=True).first(),
                            predicted_eta=eta,
                            status='PACKED'
                        )
                        if slot:
                            slot.current_orders += 1
                            slot.save()
                    except Exception as delivery_err:
                        Delivery.objects.get_or_create(order=order, status='PACKED', predicted_eta=30)

                    for item in cart_items:
                        product = item.product
                        quantity = item.quantity
                        price = item.price

                        OrderItem.objects.create(
                            order=order,
                            product=product,
                            quantity=quantity,
                            price=price
                        )

                        if product.product_type == 'piece':
                            if product.stock is None or product.stock < quantity:
                                raise ValueError(f"Not enough stock for {product.name}")

                            product.stock -= quantity
                            product.save(update_fields=['stock'])

                        else:
                            # Handle quantity-based product stock update
                            item_norm_val, item_norm_unit = normalize_quantity(item.weight, item.weight_unit)
                            
                            if not item_norm_val:
                                raise ValueError(f"Weight details missing for {product.name}")

                            qp_to_update = None
                            all_qps = product.quantity_prices.select_for_update().all()
                            
                            for qp in all_qps:
                                qp_val, qp_unit = parse_weight(qp.quantity)
                                norm_qp_val, norm_qp_unit = normalize_quantity(qp_val, qp_unit)
                                
                                if norm_qp_val == item_norm_val and norm_qp_unit == item_norm_unit:
                                    qp_to_update = qp
                                    break
                            
                            if not qp_to_update:
                                raise ValueError(f"Could not find matching variant for {product.name} ({item.weight}{item.weight_unit})")

                            if qp_to_update.stock < quantity:
                                raise ValueError(f"Not enough stock for {product.name} in {qp_to_update.quantity} variant")

                            qp_to_update.stock -= quantity
                            qp_to_update.save(update_fields=['stock'])

                    try:
                        from .ai_pantry_tracker import auto_update_pantry_on_order
                        auto_update_pantry_on_order(user, order)
                    except Exception as e:
                        print("Failed to update pantry:", e)

                    cart_items.delete()

                return render(request, 'customer/order_success.html', {
                    'order': order,
                    "total": total,
                    "address": address,
                    "city": city,
                    "postal_code": postal_code
                })

            except ValueError as e:
                messages.error(request, str(e))
                return redirect('view_cart')
            except Exception as e:
                messages.error(request, f"An error occurred: {str(e)}")
                return redirect('view_cart')

    else:
        form = CheckoutForm()

    return render(request, 'customer/checkout.html', {
        'form': form,
        'cart_total': cart_total
    })


# def payment_success(request):

#     order_id = request.session.get("order_id")
#     print("**************************",order_id)

#     order = Order.objects.get(id=order_id)
#     order_items = OrderItem.objects.filter(order=order)

#     if order.total_amount > 0:
#         points_earned = int(order.total_amount / 20)
#         try:
#             profile = CustomerProfile.objects.get(user=order.user)
#             profile.reward_points += points_earned
#             profile.save()
#             messages.success(request, f"Congratulations! You earned {points_earned} reward points matching your purchase.")
#         except CustomerProfile.DoesNotExist:
#             pass

#     return render(request,"customer/paymentsuccess.html",{
#         "order":order,
#         "order_items":order_items
#     })


def payment_success(request):

    order_id = request.session.get("order_id")
    print("**************************", order_id)

    order = Order.objects.get(id=order_id)
    order_items = OrderItem.objects.filter(order=order)

    # ✅ ADD THIS BLOCK
    for item in order_items:
        item.total_price = item.quantity * item.price

    if order.total_amount > 0:
        points_earned = int(order.total_amount / 20)
        try:
            profile = CustomerProfile.objects.get(user=order.user)
            profile.reward_points += points_earned
            profile.save()
            messages.success(
                request,
                f"Congratulations! You earned {points_earned} reward points matching your purchase."
            )
        except CustomerProfile.DoesNotExist:
            pass

    return render(request, "customer/paymentsuccess.html", {
        "order": order,
        "order_items": order_items
    })

def my_orders(request):
    user = CustomUser.objects.get(id=request.session.get("user_id"))
    orders = Order.objects.filter(user=user).order_by('-created_at').prefetch_related('items__product')
    return render(request, 'customer/my_orders.html', {'orders': orders})

def seller_restock_assistant(request):
    """
    View for the AI Product Performance & Smart Restock Assistant dashboard.
    """
    if request.session.get("user_type") != "seller":
        return redirect("login", role="seller")

    seller_id = request.session.get("user_id")
    seller_user = CustomUser.objects.get(id=seller_id)
    seller_profile = SellerProfiles.objects.get(seller=seller_user)

    result = get_restock_insights(seller_profile)
    insights = result['insights']

    top_selling = [i for i in insights if i['performance'] == "Fast Selling"]
    needs_restock = [i for i in insights if i['priority'] in ["High", "Medium"]]
    dead_stock = [i for i in insights if i['performance'] == "Dead Stock"]

    return render(request, "seller/restock_assistant.html", {
        "insights": insights,
        "top_selling_count": len(top_selling),
        "restock_count": len(needs_restock),
        "dead_stock_count": len(dead_stock),
        "no_sales_count": result['no_sales_count'],
        "efficiency_index": result['efficiency_index'],
        "most_profitable": result['most_profitable'],
        "top_category": result['top_category'],
        "seller": seller_profile,
        "insights_json": json.dumps(insights)
    })

def api_seller_restock_insights(request):
    """
    API endpoint returning restock insights as JSON.
    """
    if request.session.get("user_type") != "seller":
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=403)

    try:
        seller_id = request.session.get("user_id")
        seller_user = CustomUser.objects.get(id=seller_id)
        seller_profile = SellerProfiles.objects.get(seller=seller_user)

        result = get_restock_insights(seller_profile)
        return JsonResponse(result, safe=False)
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

from .ai_smart_search import fuzzy_product_search, extract_keywords, process_voice_command

def smart_search(request):
    query = request.GET.get('q', '')
    if query:
        nl_filters = extract_keywords(query)

        products = fuzzy_product_search(query)

        sort_by = request.GET.get('sort') or nl_filters.get('sort')

        if sort_by == "price_low_high":
            products.sort(key=lambda x: x.price)
        elif sort_by == "price_high_low":
            products.sort(key=lambda x: x.price, reverse=True)
        elif sort_by == "newest":
            products.sort(key=lambda x: x.id, reverse=True)
        elif sort_by == "sales":
            products.sort(key=lambda x: getattr(x, 'sales_count', 0), reverse=True)

        if nl_filters.get('price_limit'):
            products = [p for p in products if p.price <= nl_filters['price_limit']]

        context = {
            'products': product_data(products),
            'query': query,
            'is_smart': True
        }
        return render(request, 'customer/product_list.html', context)
    return redirect('customer_index')

@csrf_exempt
def voice_command(request):
    if request.method == "POST":
        data = json.loads(request.body)
        text = data.get("text") or data.get("command", "")
        user_id = request.session.get("user_id")

        if not user_id:
            return JsonResponse({"status": "error", "message": "Please login first."})

        result = process_voice_command(text, user_id)
        return JsonResponse(result)

def api_suggestions(request):
    query = request.GET.get('q', '').lower()
    if not query:
        return JsonResponse([], safe=False)

    products = Product.objects.all()
    product_names = [p.name for p in products]

    from rapidfuzz import process, fuzz
    matches = process.extract(query, product_names, scorer=fuzz.WRatio, limit=5)
    results = [m[0] for m in matches if m[1] > 50]

    return JsonResponse(results, safe=False)

def api_trending(request):
    trending = Product.objects.order_by('-sales_count')[:6]
    results = [p.name for p in trending]

    if len(results) < 3:
        results = ["Milk", "Bread", "Eggs", "Tomato", "Rice"]

    return JsonResponse(results, safe=False)

@csrf_exempt
def image_search(request):
    if request.method == "POST" and request.FILES.get('image'):
        from PIL import Image
        import imagehash
        from django.conf import settings
        import os

        uploaded_img = request.FILES['image']
        try:
            user_hash = imagehash.phash(Image.open(uploaded_img))
        except Exception as e:
            messages.warning(request, f"Could not process image: {str(e)}")
            return redirect('customer_index')

        all_products = Product.objects.all()
        scored_products = []

        for p in all_products:
            p_img_obj = p.images.first()
            if p_img_obj:
                try:
                    p_img_path = os.path.join(settings.MEDIA_ROOT, str(p_img_obj.image))
                    p_hash = imagehash.phash(Image.open(p_img_path))
                    distance = user_hash - p_hash
                    confidence = max(0, (64 - distance) / 64 * 100)

                    print(f"Comparing {p.name}: Distance {distance}, Confidence {confidence}%")

                    if distance < 20:
                        scored_products.append({
                            'product': p,
                            'distance': distance,
                            'confidence': round(confidence, 1)
                        })
                except Exception as e:
                    print(f"Error processing {p.name}: {e}")
                    continue

        scored_products.sort(key=lambda x: x['distance'])
        visual_matches = [item['product'] for item in scored_products]
        confidence_scores = {str(item['product'].id): item['confidence'] for item in scored_products}

        if not visual_matches:
            filename = uploaded_img.name.lower()
            clean_name = filename.split('.')[0]
            for word in ["image", "photo", "img", "upload", "shot", "pic", "scan"]:
                clean_name = clean_name.replace(word, "")

            if len(clean_name) > 2:
                from rapidfuzz import process, fuzz
                names = [p.name for p in all_products]
                matches = process.extract(clean_name, names, scorer=fuzz.WRatio, limit=3)
                for m in matches:
                    if m[1] > 70:
                        prod = all_products.get(name=m[0])
                        visual_matches.append(prod)
                        confidence_scores[str(prod.id)] = m[1]

        alternatives = []
        if not visual_matches:
            alternatives = Product.objects.all()[:4]

        return render(request, 'customer/product_list.html', {
            'products': product_data(visual_matches),
            'alternatives': product_data(alternatives),
            'query': "AI Visual Search Result",
            'is_smart': True,
            'confidence_scores': confidence_scores
        })
    return redirect('customer_index')

from django.http import JsonResponse

def api_recommendations(request, user_id):
    from .recommendations import get_personalized_recommendations
    recs = get_personalized_recommendations(user_id)
    return JsonResponse({'recommendations': recs})

def api_related_products(request, product_id):
    from .recommendations import get_related_products
    recs = get_related_products(product_id)
    return JsonResponse({'related': recs})

def api_trending_products(request):
    from .recommendations import get_trending_products
    recs = get_trending_products()
    return JsonResponse({'trending': recs})

def api_combo_products(request, product_id):
    from .recommendations import get_frequently_bought_together
    recs = get_frequently_bought_together(product_id)
    return JsonResponse({'combos': recs})

from .ai_budget_cart import optimize_budget_cart

def budget_planner(request):
    return render(request, 'customer/budget_planner.html')

@csrf_exempt
def api_budget_cart(request):
    import json
    if request.method == 'POST':
        data = json.loads(request.body)
        budget = data.get('budget', 0)
        plan_type = data.get('plan_type', 'weekly')
        family_size = data.get('family_size', 1)
        diet = data.get('diet', 'Mixed')

        result = optimize_budget_cart(budget, plan_type, family_size, diet)
        return JsonResponse(result)
    return JsonResponse({'error': 'Only POST allowed'}, status=405)

@csrf_exempt
def api_add_bulk_to_cart(request):
    import json
    if request.method == 'POST':
        if not request.session.get("user_id"):
            return JsonResponse({'status': 'error', 'message': 'Please login first'}, status=401)

        try:
            user = CustomUser.objects.get(id=request.session.get("user_id"))
            data = json.loads(request.body)
            items = data.get('items', [])

            import re

            for item in items:
                product = Product.objects.get(id=item['id'])
                price = Decimal(str(item['price']))
                qty_label = item.get('qty_label')

                weight = None
                weight_unit = None

                if product.product_type == 'quantity':
                    # Try to match by qty_label first, then by price
                    qp = None
                    if qty_label:
                         qp = product.quantity_prices.filter(quantity__iexact=qty_label).first()
                    
                    if not qp:
                        qp = product.quantity_prices.filter(price=price).first()
                    
                    if not qp:
                        qp = product.quantity_prices.order_by('price').first()

                    if qp:
                        price = qp.price
                        match = re.match(r'^([\d.]+)\s*(\w+)$', qp.quantity)
                        if match:
                            weight = Decimal(match.group(1))
                            weight_unit = match.group(2)

                qty = int(item.get('quantity', item.get('qty', 1)))

                cart_item = Cart.objects.filter(
                    user=user,
                    product=product,
                    price=price,
                    weight=weight,
                    weight_unit=weight_unit
                ).first()

                if cart_item:
                    cart_item.quantity += qty
                    cart_item.save()
                else:
                    Cart.objects.create(
                        user=user,
                        product=product,
                        price=price,
                        weight=weight,
                        weight_unit=weight_unit,
                        quantity=qty
                    )

            return JsonResponse({'status': 'success', 'message': f'Added {len(items)} items to cart'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

    return JsonResponse({'error': 'Only POST allowed'}, status=405)

from django.shortcuts import get_object_or_404, render, redirect
from .models import Notification, CustomUser

def customer_notifications(request):
    if request.session.get("user_type") != "customer":
        return redirect("login", role="customer")

    user_id = request.session.get("user_id")
    user = get_object_or_404(CustomUser, id=user_id)

    notifications = Notification.objects.filter(user=user).order_by('-created_at')

    notifications.filter(is_read=False).update(is_read=True)

    return render(request, 'customer/notifications.html', {'notifications': notifications})

from .ai_price_comparison import get_product_price_comparison, get_best_deal, get_alternative_products, get_discounted_products, get_vendor_prices

def api_discounted_products(request):
    """
    API for top discounted products across all vendors.
    """
    discounts = get_discounted_products()
    return JsonResponse({'status': 'success', 'data': discounts})



def api_product_price_comparison(request, product_id):
    """
    API for vendor price comparison table.
    """
    df = get_product_price_comparison(product_id)
    if df is not None:
        data = df.to_dict(orient='records')
        return JsonResponse({'status': 'success', 'data': data})
    return JsonResponse({'status': 'error', 'message': 'No vendor data found'}, status=404)

def api_best_deal(request, product_id):
    """
    API for best deal detection.
    """
    best = get_best_deal(product_id)
    if best:
        return JsonResponse({'status': 'success', 'best_deal': best})
    return JsonResponse({'status': 'error', 'message': 'No deal found'}, status=404)

def api_alternative_products(request, product_id):
    """
    API for cost-effective alternative suggestions.
    """
    alternatives = get_alternative_products(product_id)
    return JsonResponse({'status': 'success', 'alternatives': alternatives})

def product_price_details(request, product_id):
    """
    Page view to show the comparison UI.
    """
    product = get_object_or_404(Product, id=product_id)
    df = get_product_price_comparison(product_id)
    comparison_data = df.to_dict(orient='records') if df is not None else []
    best_deal = get_best_deal(product_id)
    alternatives = get_alternative_products(product_id)

    default_weight = None
    if product.product_type == 'quantity':
        qp = product.quantity_prices.first()
        if qp:
            default_weight = qp.quantity

    return render(request, 'customer/price_comparison_detail.html', {
        'product': product,
        'comparison': comparison_data,
        'best_deal': best_deal,
        'alternatives': alternatives,
        'default_weight': default_weight
    })


def delivery_profile(request):

    user = get_object_or_404(CustomUser, id=request.session.get("user_id"))

    profile = DeliveryPartnerProfile.objects.filter(user=user).first()

    if profile:
        return render(request, "delivery/dispprofile.html", {"profile": profile})

    if request.method == "POST":

        full_name = request.POST.get("full_name")
        phone = request.POST.get("phone")
        vehicle_type = request.POST.get("vehicle_type")
        vehicle_number = request.POST.get("vehicle_number")
        working_city = request.POST.get("working_city")
        address = request.POST.get("address")
        latitude = request.POST.get("latitude")
        longitude = request.POST.get("longitude")

        if not phone or not phone.isdigit() or len(phone) != 10:
            messages.error(request, "Phone number must be exactly 10 digits.")
            return render(request, "delivery/profile creation.html")

        DeliveryPartnerProfile.objects.create(
            user=user,
            full_name=full_name,
            phone=phone,
            vehicle_type=vehicle_type,
            vehicle_number=vehicle_number,
            working_city=working_city,
            address=address,
            latitude=latitude,
            longitude=longitude
        )

        return redirect("delivery_index")

    return render(request, "delivery/profile creation.html")
from django.shortcuts import render, redirect, get_object_or_404

#
# def deliveryindex(request):
#
#     user_id = request.session.get("user_id")
#
#     if not user_id:
#         return redirect("login")
#
#     user = get_object_or_404(CustomUser, id=user_id)
#
#     profile = DeliveryPartnerProfile.objects.filter(user=user).first()
#
#     if not profile:
#         return redirect("delivery_profile")
#     nearby_orders = []
#     if profile.is_active:
#
#         partner_lat = profile.latitude
#         partner_lon = profile.longitude
#
#
#
#         orders = Order.objects.filter(status="ordered")
#
#         for order in orders:
#
#             try:
#                 customer_profile = order.user.customerprofile
#
#                 customer_lat = customer_profile.latitude
#                 customer_lon = customer_profile.longitude
#
#                 distance = calculate_distance(
#                     partner_lat,
#                     partner_lon,
#                     customer_lat,
#                     customer_lon
#                 )
#
#                 if distance <= 3:
#                     order.distance = round(distance, 2)
#                     nearby_orders.append(order)
#
#             except CustomerProfile.DoesNotExist:
#                 continue
#
#     return render(
#         request,
#         "delivery/index.html",
#         {
#             "profile": profile,
#             "orders": nearby_orders
#         }
#     )


#
# def deliveryindex(request):
#
#     user_id = request.session.get("user_id")
#
#     if not user_id:
#         return redirect("login")
#
#     user = get_object_or_404(CustomUser, id=user_id)
#
#     profile = DeliveryPartnerProfile.objects.filter(user=user).first()
#
#     if not profile:
#         return redirect("delivery_profile")
#
#     nearby_orders = []
#     my_deliveries = []
#
#     # ✅ Get deliveries assigned to this partner
#     my_deliveries = Delivery.objects.filter(agent=profile).select_related('order', 'slot')
#
#     if profile.is_active:
#
#         partner_lat = profile.latitude
#         partner_lon = profile.longitude
#
#         orders = Order.objects.filter(status="ordered")
#
#         for order in orders:
#             try:
#                 customer_profile = order.user.customerprofile
#
#                 distance = calculate_distance(
#                     partner_lat,
#                     partner_lon,
#                     customer_profile.latitude,
#                     customer_profile.longitude
#                 )
#
#                 if distance <= 3:
#                     order.distance = round(distance, 2)
#                     nearby_orders.append(order)
#
#             except CustomerProfile.DoesNotExist:
#                 continue
#
#     return render(
#         request,
#         "delivery/index.html",
#         {
#             "profile": profile,
#             "orders": nearby_orders,      # nearby orders to accept
#             "my_deliveries": my_deliveries  # ✅ assigned deliveries
#         }
#     )
from collections import defaultdict
from django.utils.timezone import localtime

def deliveryindex(request):

    user_id = request.session.get("user_id")

    if not user_id:
        return redirect("login")

    user = get_object_or_404(CustomUser, id=user_id)

    profile = DeliveryPartnerProfile.objects.filter(user=user).first()

    if not profile:
        return redirect("delivery_profile")

    nearby_orders = []

    # ✅ Fetch deliveries with tracking logs
    deliveries = Delivery.objects.filter(agent=profile) \
        .select_related('order', 'slot') \
        .prefetch_related('tracking_logs')

    for d in deliveries:
        d.logs = list(d.tracking_logs.all())

        # ✅ Group deliveries by date
    deliveries_by_date = defaultdict(list)

    for d in deliveries:
        d.logs = list(d.tracking_logs.all())  # already correct

        # ✅ FIXED DATE (stable)
        date = localtime(d.order.created_at).date()

        deliveries_by_date[date].append(d)

    # ✅ Nearby orders logic
    if profile.is_active:

        partner_lat = profile.latitude
        partner_lon = profile.longitude

        orders = Order.objects.filter(status="ordered")

        for order in orders:
            try:
                customer_profile = order.user.customerprofile

                distance = calculate_distance(
                    partner_lat,
                    partner_lon,
                    customer_profile.latitude,
                    customer_profile.longitude
                )

                if distance <= 3:
                    order.distance = round(distance, 2)
                    nearby_orders.append(order)

            except CustomerProfile.DoesNotExist:
                continue

    return render(
        request,
        "delivery/index.html",
        {
            "profile": profile,
            "orders": nearby_orders,
            "deliveries_by_date": dict(deliveries_by_date)  # ✅ grouped data
        }
    )
def accept_order(request, order_id):

    user_id = request.session.get("user_id")

    if not user_id:
        return redirect("login")

    user = get_object_or_404(CustomUser, id=user_id)
    order = get_object_or_404(Order, id=order_id)

    order.status = "assigned_delivery"
    order.delivery_partner = user
    order.save()

    try:
        partner_profile = DeliveryPartnerProfile.objects.filter(user=user).first()

        delivery, created = Delivery.objects.get_or_create(
            order=order,
            defaults={"distance_km": 5.0, "traffic_level": "MEDIUM"}
        )

        if partner_profile:
            partner_profile.is_available = False
            partner_profile.save()

            delivery.agent = partner_profile
            delivery.status = "PACKED"
            delivery.save()

            if not DeliveryTracking.objects.filter(delivery=delivery).exists():
                DeliveryTracking.objects.create(
                    delivery=delivery, status="PACKED",
                    lat=partner_profile.latitude or 10.02, lng=partner_profile.longitude or 76.31,
                    location_name="Order Accepted"
                )
    except Exception as e:
        print("Delivery AI linking failed:", str(e))

    return redirect("delivery_index")

def assigned_orders(request):

    user_id = request.session.get("user_id")

    if not user_id:
        return redirect("login")

    user = get_object_or_404(CustomUser, id=user_id)

    orders = Order.objects.filter(
        delivery_partner=user,
        status="assigned_delivery"
    )

    return render(request, "delivery/assigned_orders.html", {"orders": orders})

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

def verify_delivery_otp(request, order_id):
    user_id = request.session.get("user_id")

    if not user_id:
        return redirect("login")

    user = get_object_or_404(CustomUser, id=user_id)

    profile = DeliveryPartnerProfile.objects.filter(user=user).first()

    order = get_object_or_404(Order, id=order_id)

    if request.method == "POST":

        entered_otp = request.POST.get("otp")

        if entered_otp == order.otp:

            order.status = "Delivered"
            order.save()

            try:
                delivery = Delivery.objects.get(order=order)
                delivery.status = "DELIVERED"
                delivery.agent=profile
                delivery.save()

                if delivery.agent:
                    delivery.agent.is_available = True
                    delivery.agent.save()

                Notification.objects.create(
                    user=order.user,
                    title="Order Delivered",
                    message="Your order has been delivered successfully. Thank you!"
                )

                DeliveryTracking.objects.create(
                    delivery=delivery, status="DELIVERED",
                    lat=delivery.agent.latitude if delivery.agent and delivery.agent.latitude else 12.97,
                    lng=delivery.agent.longitude if delivery.agent and delivery.agent.longitude else 77.59
                )
            except Exception as e:
                pass

            messages.success(request, "Delivery completed successfully")
            return redirect("assigned_orders")

        else:
            messages.error(request, "Invalid OTP")

    return redirect("assigned_orders")

def driver_update_status(request, delivery_id, status):
    """ Allows a driver to update an order's status before completing it via OTP """
    if request.session.get("user_type") != "delivery":
        pass

    delivery = get_object_or_404(Delivery, id=delivery_id)
    if status in ['DISPATCHED', 'NEARBY']:
        delivery.status = status
        delivery.save()

        lat = delivery.agent.latitude if delivery.agent and delivery.agent.latitude else 12.97
        lng = delivery.agent.longitude if delivery.agent and delivery.agent.longitude else 77.59
        DeliveryTracking.objects.create(
            delivery=delivery, status=status,
            lat=lat, lng=lng,
            location_name="Updated by Agent"
        )

        if status == 'DISPATCHED':
            msg = "Your order is on the way! The agent is heading towards you."
        else:
            msg = "The delivery agent is nearby! Please be ready to receive your order."

        Notification.objects.create(
            user=delivery.order.user,
            title=f"Order",
            message=msg
        )
        messages.success(request, f"Status updated to '{status}'")

    return redirect("assigned_orders")



@csrf_exempt
def update_agent_location(request):
    """
    API: Delivery agent sends GPS location.
    POST /api/update-location/
    Body: { "agent_id": 12, "latitude": 10.01234, "longitude": 76.34521 }
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST only"}, status=405)

    data = json.loads(request.body)
    agent_id = data.get("agent_id")
    lat = data.get("latitude")
    lng = data.get("longitude")

    if not all([agent_id, lat, lng]):
        return JsonResponse({"status": "error", "message": "Missing fields"}, status=400)

    try:
        agent = DeliveryAgent.objects.get(id=agent_id)
        agent.current_lat = lat
        agent.current_lng = lng
        agent.save()
    except DeliveryAgent.DoesNotExist:
        pass

    try:
        user_id = request.session.get("user_id")
        if user_id:
            profile = DeliveryPartnerProfile.objects.get(user_id=user_id)
            profile.latitude = lat
            profile.longitude = lng
            profile.save()
    except DeliveryPartnerProfile.DoesNotExist:
        pass

    active_deliveries = Delivery.objects.filter(
        agent_id=agent_id,
        status__in=["PACKED", "DISPATCHED", "NEARBY"]
    )
    for d in active_deliveries:
        DeliveryTracking.objects.create(
            delivery=d,
            status=d.status,
            lat=lat,
            lng=lng,
            location_name="Live GPS Update"
        )

    return JsonResponse({
        "status": "success",
        "message": "Location updated",
        "lat": lat,
        "lng": lng
    })


def track_delivery_live(request, order_id):
    """
    Enhanced delivery tracking page with real Leaflet.js map.
    """
    order = get_object_or_404(Order, id=order_id)

    if not DeliveryAgent.objects.exists():
        agents_data = [
            {"name": "Rahul Sharma", "phone": "9876543210", "vehicle": "KA-01-EB-1234"},
            {"name": "Amit Kumar", "phone": "9123456780", "vehicle": "KA-03-GH-5678"},
            {"name": "Priya Singh", "phone": "9988776655", "vehicle": "KA-05-JK-9012"},
        ]
        for a in agents_data:
            DeliveryAgent.objects.get_or_create(
                name=a["name"], phone=a["phone"],
                vehicle_number=a["vehicle"], is_available=True
            )

    try:
        delivery = Delivery.objects.get(order=order)
    except Delivery.DoesNotExist:
        delivery = Delivery.objects.create(
            order=order, distance_km=5.0, traffic_level="MEDIUM"
        )

    from .ai_eta_prediction import predict_eta as ai_predict_eta, calculate_distance as ai_calc_dist

    store_lat, store_lng = 10.0261, 76.3125
    try:
        first_item = order.items.first()
        if first_item and first_item.product.seller:
            seller = first_item.product.seller
            if seller.latitude and seller.longitude:
                store_lat = seller.latitude
                store_lng = seller.longitude
    except Exception:
        pass

    if not delivery.agent:
        agent = DeliveryPartnerProfile.objects.filter(is_available=True).first()
        if agent:
            if agent.latitude is None:
                agent.latitude = store_lat
            if agent.longitude is None:
                agent.longitude = store_lng
            agent.save()

            delivery.agent = agent
            delivery.save()
            if not DeliveryTracking.objects.filter(delivery=delivery).exists():
                DeliveryTracking.objects.create(
                    delivery=delivery, status="PACKED",
                    lat=store_lat, lng=store_lng
                )
    else:
        if delivery.agent.latitude and delivery.agent.longitude:
            pass
        else:
            delivery.agent.latitude = store_lat
            delivery.agent.longitude = store_lng
            delivery.agent.save()

    cust_lat, cust_lng = store_lat + 0.01, store_lng + 0.01
    try:
        cust_profile = CustomerProfile.objects.get(user=order.user)
        cust_lat = cust_profile.latitude
        cust_lng = cust_profile.longitude
    except CustomerProfile.DoesNotExist:
        pass

    agent_lat = delivery.agent.latitude if delivery.agent and delivery.agent.latitude else store_lat
    agent_lng = delivery.agent.longitude if delivery.agent and delivery.agent.longitude else store_lng

    distance = ai_calc_dist(agent_lat, agent_lng, cust_lat, cust_lng)

    active_orders_count = 1
    if delivery.agent:
        active_orders_count = Delivery.objects.filter(
            agent=delivery.agent,
            status__in=["PACKED", "DISPATCHED", "NEARBY"]
        ).count()

    eta_result = ai_predict_eta(distance, delivery.traffic_level, active_orders_count)
    delivery.predicted_eta = eta_result["predicted_eta_mins"]
    delivery.distance_km = distance
    delivery.save()


    tracking_logs = DeliveryTracking.objects.filter(delivery=delivery).order_by("-timestamp")

    status_steps = [
        {"key": "PACKED", "label": "Order Packed", "icon": "📦"},
        {"key": "DISPATCHED", "label": "Out for Delivery", "icon": "🚚"},
        {"key": "NEARBY", "label": "Near Your Location", "icon": "📍"},
        {"key": "DELIVERED", "label": "Delivered", "icon": "✅"},
    ]
    status_order = ["PACKED", "DISPATCHED", "NEARBY", "DELIVERED"]
    current_idx = status_order.index(delivery.status) if delivery.status in status_order else 0
    for i, step in enumerate(status_steps):
        step["done"] = i <= current_idx
        step["current"] = i == current_idx

    return render(request, "customer/track_delivery_live.html", {
        "order": order,
        "delivery": delivery,
        "logs": tracking_logs,
        "eta_result": eta_result,
        "store_lat": store_lat,
        "store_lng": store_lng,
        "cust_lat": cust_lat,
        "cust_lng": cust_lng,
        "agent_lat": agent_lat,
        "agent_lng": agent_lng,
        "status_steps": status_steps,
    })


def api_agent_location(request, order_id):
    """
    API: Returns the current agent location for live map polling.
    """
    try:
        delivery = Delivery.objects.get(order_id=order_id)
    except Delivery.DoesNotExist:
        return JsonResponse({"status": "error"}, status=404)

    agent_lat = delivery.agent.latitude if delivery.agent and delivery.agent.latitude else 10.0261
    agent_lng = delivery.agent.longitude if delivery.agent and delivery.agent.longitude else 76.3125

    cust_lat, cust_lng = agent_lat + 0.01, agent_lng + 0.01
    try:
        cust_profile = CustomerProfile.objects.get(user=delivery.order.user)
        cust_lat = cust_profile.latitude
        cust_lng = cust_profile.longitude
    except CustomerProfile.DoesNotExist:
        pass

    import random
    if delivery.status in ["DISPATCHED", "NEARBY"]:
        move_factor = 0.05
        agent_lat += (cust_lat - agent_lat) * move_factor + random.uniform(-0.0005, 0.0005)
        agent_lng += (cust_lng - agent_lng) * move_factor + random.uniform(-0.0005, 0.0005)
        if delivery.agent:
            delivery.agent.latitude = agent_lat
            delivery.agent.longitude = agent_lng
            delivery.agent.save()

    return JsonResponse({
        "status": "success",
        "delivery_status": delivery.status,
        "agent_name": delivery.agent.full_name if delivery.agent else "Assigning...",
        "agent_phone": delivery.agent.phone if delivery.agent else "",

        "agent_lat": agent_lat,
        "agent_lng": agent_lng,
        "eta": delivery.predicted_eta,
    })


def admin_delivery_dashboard(request):
    """
    Admin Delivery Monitoring Dashboard.
    Shows active deliveries, available agents, delayed deliveries, and ETA predictions.
    """
    if not request.user.is_superuser and request.session.get("user_type") != "admin":
        return redirect("adminlogin")

    all_deliveries = Delivery.objects.select_related("order", "agent", "slot").order_by("-order__created_at")

    active_deliveries = all_deliveries.filter(status__in=["PACKED", "DISPATCHED", "NEARBY"])

    completed_deliveries = all_deliveries.filter(status="DELIVERED")

    delayed_deliveries = active_deliveries.filter(predicted_eta__gt=45)

    available_agents = DeliveryAgent.objects.filter(is_available=True)
    all_agents = DeliveryAgent.objects.all()

    delivery_partners = DeliveryPartnerProfile.objects.select_related("user").all()
    active_partners = delivery_partners.filter(is_active=True, is_available=True)

    orders_in_transit = Order.objects.filter(status__in=["assigned_delivery", "shipped"])

    stats = {
        "total_deliveries": all_deliveries.count(),
        "active_deliveries": active_deliveries.count(),
        "completed_deliveries": completed_deliveries.count(),
        "delayed_deliveries": delayed_deliveries.count(),
        "available_agents": available_agents.count(),
        "total_agents": all_agents.count(),
        "orders_in_transit": orders_in_transit.count(),
        "active_partners": active_partners.count(),
    }

    return render(request, "admin/delivery_dashboard.html", {
        "stats": stats,
        "active_deliveries": active_deliveries,
        "completed_deliveries": completed_deliveries[:20],
        "delayed_deliveries": delayed_deliveries,
        "available_agents": available_agents,
        "all_agents": all_agents,
        "delivery_partners": delivery_partners,
        "orders_in_transit": orders_in_transit,
    })


@csrf_exempt
def admin_reassign_delivery(request, delivery_id):
    """
    Admin can reassign a delivery to a different agent.
    """
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "POST only"}, status=405)

    data = json.loads(request.body)
    new_agent_id = data.get("agent_id")

    delivery = get_object_or_404(Delivery, id=delivery_id)
    new_agent = get_object_or_404(DeliveryAgent, id=new_agent_id)

    if delivery.agent:
        delivery.agent.is_available = True
        delivery.agent.save()

    delivery.agent = new_agent
    delivery.save()
    new_agent.is_available = False
    new_agent.save()

    Notification.objects.create(
        user=delivery.order.user,
        title=f"Order",
        message=f"Your delivery agent has been changed to {new_agent.full_name}."
    )

    DeliveryTracking.objects.create(
        delivery=delivery,
        status=delivery.status,
        lat=new_agent.latitude or 10.0261,
        lng=new_agent.longitude or 76.3125,
        location_name=f"Reassigned to {new_agent.full_name}"
    )

    return JsonResponse({"status": "success", "agent_name": new_agent.full_name})



from .ai_pantry_tracker import get_user_pantry, detect_low_stock, predict_days_remaining, calculate_daily_usage, generate_reorder_alerts
from .models import UserPantry, PantryUsage

def my_smart_pantry(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return redirect('login')

    generate_reorder_alerts(user_id)

    pantry_items = get_user_pantry(user_id)

    pantry_data = []
    for item in pantry_items:
        days_left = predict_days_remaining(user_id, item.product.id)
        daily_usage = calculate_daily_usage(user_id, item.product.id)

        status = "Good"
        status_color = "success"

        if item.quantity < item.threshold:
            status = "Low Stock"
            status_color = "danger"
        elif days_left <= 3:
            status = "Running Out"
            status_color = "warning"

        prod_reviews = item.product.reviews.all()
        avg_r = prod_reviews.aggregate(models.Avg('rating'))['rating__avg'] or 0.0
        avg_r = round(float(avg_r), 1)
        rev_count = prod_reviews.count()

        pantry_data.append({
            "pantry_id": item.id,
            "product": item.product,
            "quantity": item.quantity,
            "unit": item.unit,
            "days_left": str(days_left) if days_left != 999 else "30+",
            "daily_usage": daily_usage,
            "status": status,
            "status_color": status_color,
            "avg_rating": avg_r,
            "review_count": rev_count
        })

    alerts = detect_low_stock(user_id)
    all_products = Product.objects.all()

    return render(request, "customer/my_pantry.html", {
        "pantry_data": pantry_data,
        "alerts": alerts,
        "all_products": all_products
    })

@csrf_exempt
def api_add_to_pantry(request):
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid request"}, status=400)

    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    try:
        data = json.loads(request.body)
        product_id = data.get("product_id")
        quantity = float(data.get("quantity", 0))
        unit = data.get("unit", "packs")

        user = CustomUser.objects.get(id=user_id)
        product = Product.objects.get(id=product_id)

        pantry_item, created = UserPantry.objects.get_or_create(
            user=user,
            product=product,
            defaults={'quantity': 0, 'unit': unit, 'threshold': 1.0}
        )
        pantry_item.quantity += quantity
        pantry_item.unit = unit
        pantry_item.save()

        return JsonResponse({"status": "success", "message": "Added to pantry"})
    except Exception as e:
        return JsonResponse({"status": "error", "message": str(e)}, status=400)

@csrf_exempt
def api_check_low_stock(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    alerts = detect_low_stock(user_id)
    return JsonResponse({"status": "success", "alerts": alerts})

def api_get_pantry(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({"status": "error", "message": "Unauthorized"}, status=401)

    pantry_items = get_user_pantry(user_id)
    data = []
    for item in pantry_items:
        data.append({
            "product_id": item.product.id,
            "product_name": item.product.name,
            "quantity": item.quantity,
            "unit": item.unit
        })

    return JsonResponse({"status": "success", "pantry": data})

from django.core.paginator import Paginator

def products_page(request):
    """
    Renders the Product & Category Management module page.
    """
    categories = Category.objects.values('CategoryName').distinct().order_by('CategoryName')
    brands = Brands.objects.values('brandName').distinct().order_by('brandName')

    return render(request, "customer/products.html", {
        "categories": categories,
        "brands": brands
    })

@csrf_exempt
def filter_products_api(request):
    """
    API for filtering, sorting and paginating products.
    Takes JSON request with: category, brand, sort, page.
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            category_name = data.get("category")
            brand_name = data.get("brand")
            sort_by = data.get("sort")
            page_num = int(data.get("page", 1))

            products = Product.objects.all()

            if category_name:
                products = products.filter(category__CategoryName=category_name)

            if brand_name:
                products = products.filter(brand__brandName=brand_name)

            if sort_by == "price_low_high":
                products = products.order_by("price")
            elif sort_by == "price_high_low":
                products = products.order_by("-price")
            elif sort_by == "newest":
                products = products.order_by("-id")
            elif sort_by == "oldest":
                products = products.order_by("id")

            paginator = Paginator(products, 20)
            page_obj = paginator.get_page(page_num)

            product_list = product_data(page_obj.object_list)

            return JsonResponse({
                "products": product_list,
                "has_next": page_obj.has_next(),
                "current_page": page_obj.number,
                "total_pages": paginator.num_pages
            })
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)

    elif request.method == "GET":
        products = Product.objects.all()
        paginator = Paginator(products, 20)
        page_obj = paginator.get_page(int(request.GET.get('page', 1)))
        return JsonResponse({
            "products": product_data(page_obj.object_list)
        })

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def add_review(request):
    if request.method == "POST":
        user_id = request.session.get('user_id')
        if not user_id:
            messages.error(request, "Please log in to submit a review.")
            return redirect('login', role='customer')

        product_id = request.POST.get("product_id")
        rating = request.POST.get("rating")
        comment = request.POST.get("comment")

        user = CustomUser.objects.get(id=user_id)
        product = get_object_or_404(Product, id=product_id)

        has_purchased = Order.objects.filter(
            user=user,
            status__iexact="Delivered",
            items__product=product
        ).exists()

        if not has_purchased:
            messages.error(request, "You can only review products you have purchased and received.")
            return redirect('product_detail', product_id=product.id)

        review, created = Review.objects.update_or_create(
            user=user,
            product=product,
            defaults={'rating': rating, 'comment': comment}
        )

        messages.success(request, "Thank you! Your review has been submitted.")
        return redirect('product_detail', product_id=product.id)

def get_product_reviews(request, product_id):
    reviews = Review.objects.filter(product_id=product_id).select_related('user').order_by('-created_at')
    data = []
    for r in reviews:
        data.append({
            "user": r.user.username,
            "rating": r.rating,
            "comment": r.comment,
            "date": r.created_at.strftime('%Y-%m-%d')
        })
    return JsonResponse({"status": "success", "reviews": data})

def get_average_rating(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    avg_rating = product.reviews.aggregate(Avg('rating'))['rating__avg'] or 0.0
    count = product.reviews.count()
    return JsonResponse({
        "status": "success",
        "average": round(float(avg_rating), 1),
        "total_reviews": count
    })

from django.db.models import Sum
from django.db.models.functions import TruncDay

def admin_daily_sales_report(request):
    """
    Returns daily sales total for Chart.js admin dashboard.
    """
    daily_sales = (
        Order.objects.annotate(day=TruncDay('created_at'))
        .values('day')
        .annotate(total_sales=Sum('total_amount'))
        .order_by('day')
    )

    days = []
    sales = []
    for sale in daily_sales:
        if sale['day']:
            days.append(sale['day'].strftime('%a'))
            sales.append(float(sale['total_sales'] or 0))

    return JsonResponse({"days": days, "sales": sales})

def seller_sales_report(request, seller_id):
    """
    Returns daily sales total specifically for a seller's products for their dashboard.
    """
    seller = get_object_or_404(SellerProfiles, id=seller_id)

    daily_sales = (
        OrderItem.objects.filter(product__seller=seller)
        .annotate(day=TruncDay('order__created_at'))
        .values('day')
        .annotate(total_sales=Sum('price'))
        .order_by('day')
    )

    days = []
    sales = []
    for sale in daily_sales:
        if sale['day']:
            days.append(sale['day'].strftime('%a'))
            sales.append(float(sale['total_sales'] or 0))

    return JsonResponse({"days": days, "sales": sales})

@csrf_exempt
def api_generate_seller_report(request):
    if request.session.get("user_type") != "admin":
        if not request.user.is_superuser:
            return JsonResponse({"error": "Unauthorized"}, status=403)

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            seller_id = data.get("seller_id")
            report_type = data.get("report_type", "daily")
            start_date = data.get("start_date")
            end_date = data.get("end_date")

            seller = get_object_or_404(SellerProfiles, id=seller_id)

            query = OrderItem.objects.filter(product__seller=seller)

            if start_date and end_date:
                query = query.filter(order__created_at__date__range=[start_date, end_date])

            if report_type == "daily":
                results = (
                    query.annotate(label=TruncDay('order__created_at'))
                    .values('label')
                    .annotate(
                        orders=Count('order', distinct=True),
                        sales=Sum(F('price') * F('quantity'))
                    )
                    .order_by('label')
                )
            elif report_type == "monthly":
                results = (
                    query.annotate(label=TruncMonth('order__created_at'))
                    .values('label')
                    .annotate(
                        orders=Count('order', distinct=True),
                        sales=Sum(F('price') * F('quantity'))
                    )
                    .order_by('label')
                )
            elif report_type == "yearly":
                results = (
                    query.annotate(label=TruncYear('order__created_at'))
                    .values('label')
                    .annotate(
                        orders=Count('order', distinct=True),
                        sales=Sum(F('price') * F('quantity'))
                    )
                    .order_by('label')
                )
            else:
                return JsonResponse({"error": "Invalid report type"}, status=400)

            labels = []
            orders_list = []
            sales_list = []

            for r in results:
                if not r['label']: continue

                if report_type == "daily":
                    labels.append(r['label'].strftime('%Y-%m-%d'))
                elif report_type == "monthly":
                    labels.append(r['label'].strftime('%b %Y'))
                elif report_type == "yearly":
                    labels.append(r['label'].strftime('%Y'))

                orders_list.append(r['orders'])
                sales_list.append(float(r['sales'] or 0))

            return JsonResponse({
                "labels": labels,
                "orders": orders_list,
                "sales": sales_list,
                "seller_name": seller.display_name
            })
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)

@csrf_exempt
def admin_delivery_report(request):
    if request.session.get("user_type") != "admin":
        if not request.user.is_superuser:
            return redirect("adminlogin")

    partners = DeliveryAgent.objects.all()
    return render(request, "admin/delivery_report.html", {"partners": partners})

@csrf_exempt
def api_delivery_report(request):
    if request.session.get("user_type") != "admin":
        if not request.user.is_superuser:
            return JsonResponse({"error": "Unauthorized"}, status=403)

    report_date_str = request.GET.get('report_date')
    partner_id = request.GET.get('partner_id')

    query = Delivery.objects.all()

    if report_date_str:
        query = query.filter(order__created_at__date=report_date_str)
    else:
        today = date.today()
        query = query.filter(order__created_at__date=today)

    if partner_id and partner_id != "all":
        query = query.filter(agent_id=partner_id)

    total_deliveries = query.count()
    delivered_query = query.filter(status='DELIVERED')
    delivered = delivered_query.count()
    pending = query.filter(status__in=['PACKED', 'NEARBY']).count()
    out_for_delivery = query.filter(status='DISPATCHED').count()
    cancelled = query.filter(order__status='Cancelled').count()

    total_sales = delivered_query.aggregate(total=Sum('order__total_amount'))['total'] or 0

    delivery_list = []
    for d in query.select_related('order', 'agent').order_by('-order__created_at'):
        delivery_list.append({
            "order_id": d.order.id,
            "partner": d.agent.name if d.agent else "Not Assigned",
            "status": d.status if d.order.status != 'Cancelled' else 'CANCELLED',
            "time": d.order.created_at.strftime("%Y-%m-%d %I:%M %p"),
            "amount": float(d.order.total_amount)
        })

    return JsonResponse({
        "total_deliveries": total_deliveries,
        "delivered": delivered,
        "pending": pending,
        "out_for_delivery": out_for_delivery,
        "cancelled": cancelled,
        "total_sales": float(total_sales),
        "deliveries": delivery_list
    })

@csrf_exempt
def api_admin_seller_report(request):
    import json
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            seller_id = data.get('seller_id')
            report_type = data.get('report_type')
            start_date = data.get('start_date')
            end_date = data.get('end_date')

            order_items = OrderItem.objects.filter(product__seller_id=seller_id, order__status__iexact='delivered')

            if start_date:
                order_items = order_items.filter(order__created_at__date__gte=start_date)
            if end_date:
                order_items = order_items.filter(order__created_at__date__lte=end_date)

            labels = []
            orders_list = []
            sales_list = []

            if report_type == 'daily':
                grouped = order_items.annotate(date=TruncDay('order__created_at')).values('date').annotate(
                    total_orders=Count('order', distinct=True),
                    total_sales=Sum(F('price') * F('quantity'), output_field=DecimalField(max_digits=10, decimal_places=2))
                ).order_by('date')
                for item in grouped:
                    if item['date']:
                        labels.append(item['date'].strftime('%Y-%m-%d'))
                        orders_list.append(item['total_orders'])
                        sales_list.append(float(item['total_sales'] or 0))

            elif report_type == 'monthly':
                grouped = order_items.annotate(month=TruncMonth('order__created_at')).values('month').annotate(
                    total_orders=Count('order', distinct=True),
                    total_sales=Sum(F('price') * F('quantity'), output_field=DecimalField(max_digits=10, decimal_places=2))
                ).order_by('month')
                for item in grouped:
                    if item['month']:
                        labels.append(item['month'].strftime('%b %Y'))
                        orders_list.append(item['total_orders'])
                        sales_list.append(float(item['total_sales'] or 0))

            elif report_type == 'yearly':
                grouped = order_items.annotate(year=TruncYear('order__created_at')).values('year').annotate(
                    total_orders=Count('order', distinct=True),
                    total_sales=Sum(F('price') * F('quantity'), output_field=DecimalField(max_digits=10, decimal_places=2))
                ).order_by('year')
                for item in grouped:
                    if item['year']:
                        labels.append(item['year'].strftime('%Y'))
                        orders_list.append(item['total_orders'])
                        sales_list.append(float(item['total_sales'] or 0))

            return JsonResponse({
                'labels': labels,
                'orders': orders_list,
                'sales': sales_list
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

def seasonal_packs(request):
    packs = SeasonalPack.objects.filter(is_active=True)
    return render(request, "customer/seasonal_packs.html", {"packs": packs})

def add_pack_to_cart(request, pack_id):
    if request.session.get("user_type") != "customer":
        return redirect("login", role="customer")

    pack = get_object_or_404(SeasonalPack, id=pack_id)
    user = CustomUser.objects.get(id=request.session.get("user_id"))

    for product in pack.products.all():
        Cart.objects.get_or_create(user=user, product=product)

    messages.success(request, f"Festival Pack '{pack.name}' added to your cart!")
    return redirect("view_cart")

def family_group_manage(request):
    if request.session.get("user_type") != "customer":
        return redirect("login", role="customer")

    user = CustomUser.objects.get(id=request.session.get("user_id"))
    group = FamilyGroup.objects.filter(members=user).first() or FamilyGroup.objects.filter(admin=user).first()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            name = request.POST.get("group_name")
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            new_group = FamilyGroup.objects.create(admin=user, group_name=name, group_code=code)
            new_group.members.add(user)
            messages.success(request, f"Family Group '{name}' created! Share code: {code}")
        elif action == "join":
            code = request.POST.get("group_code")
            try:
                group_to_join = FamilyGroup.objects.get(group_code=code)
                group_to_join.members.add(user)
                messages.success(request, f"Joined family group: {group_to_join.group_name}")
            except FamilyGroup.DoesNotExist:
                messages.error(request, "Invalid group code")
        return redirect("family_group_manage")

    return render(request, "customer/family_groups.html", {"group": group})
