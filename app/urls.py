from django.urls import path
from .views import *

urlpatterns=[
    path('',index,name="index"),
    path('logout/', logout_view, name='logout'),


    path('adminlogin/', adminlogin, name="adminlogin"),
    path("admin_dashboard/", admin_dashboard, name="admin_dashboard"),
    path('approve-seller/<int:id>/', approve_seller, name='approve_seller'),
    path('admin-intel/seller-analysis/', admin_seller_analysis, name='admin_seller_analysis'),
    path('admin-intel/seller-report/<int:seller_id>/', admin_seller_report, name='admin_seller_report'),
    path('api/admin/seller-report/', api_admin_seller_report, name='api_admin_seller_report'),
    path('admin/complaints/', admin_manage_complaints, name='admin_manage_complaints'),
    path('commission-details/', commission_details, name="commission_details"),

    path('register/<str:role>', register, name='register'),
    path("login/<str:role>",login, name="login"),


    path("seller/index/", seller_index, name="seller_index"),
    path("sellerindex/",sellerindex,name="sellerindex"),
    path('seller_profile/', create_seller_profile, name='create_seller_profile'),
    path('reverse-geocode/', reverse_geocode, name='reverse_geocode'),
    path("seller_profile_disp/", seller_profile_display, name="seller_profile_display"),

    path('seller/categories/', manage_category, name='manage_category'),
    path('seller/category/delete/<int:cat_id>/', delete_category, name='delete_category'),

    path('seller/brands/', manage_brands, name='manage_brands'),
    path('seller/brand/delete/<int:brand_id>/', delete_brand, name='delete_brand'),

    path('seller/products/', add_product, name='manage_products'),
    path('seller/product/delete/<int:product_id>/', delete_product, name='delete_product'),
    path('seller/performance/', product_performance, name='product_performance'),
    path('seller/intelligence/', seller_intelligence, name='seller_intelligence'),
    path('seller/apply-discount/', apply_seller_discount, name='apply_seller_discount'),
    path('seller/restock/', seller_restock_assistant, name='seller_restock_assistant'),
    path('api/seller/restock-insights/', api_seller_restock_insights, name='api_seller_restock_insights'),
    path('seller/summarize/', summarize_performance, name='summarize_performance'),
    path('seller/chat/', seller_ai_chat, name='seller_ai_chat'),


    path('customer_index',customer_index,name="customer_index"),
path("customer/create-profile/", create_customer_profile, name="create_customer_profile"),
    path('product-list/', product_list, name='product_list'),
    path('product/<int:product_id>/', product_detail, name='product_detail'),
    path('add-to-cart/<int:product_id>/', add_to_cart, name='add_to_cart'),
    path('add-to-wishlist/<int:product_id>/',add_to_wishlist, name='add_to_wishlist'),
    path('wishlist/',view_wishlist, name='view_wishlist'),
    path('cart/', view_cart, name='view_cart'),
    path('cart/remove/<int:product_id>/', remove_from_cart, name='remove_from_cart'),
    path('cart/update/<int:cart_id>/<str:action>/', update_cart_quantity, name='update_cart_quantity'),
    path('checkout/<str:total>', checkout, name='checkout'),
    path('my_orders/', my_orders, name='my_orders'),
    path('submit_complaint/', submit_complaint, name='submit_complaint'),
    path('my_complaints/', customer_complaints, name='customer_complaints'),
    path('seller/complaints/', seller_complaints, name='seller_complaints'),
    path('smart_search/', smart_search, name='smart_search'),
    path('voice_command/', voice_command, name='voice_command'),
    path('image_search/', image_search, name='image_search'),

    path("/payment-success/",payment_success,name="payment_success"),

    path('api/recommendations/<int:user_id>/', api_recommendations, name='api_recommendations'),
    path('api/product/<int:product_id>/related/', api_related_products, name='api_related_products'),
    path('api/trending/', api_trending_products, name='api_trending_products'),
    path('api/product/<int:product_id>/combo/', api_combo_products, name='api_combo_products'),

    path('budget-planner/', budget_planner, name='budget_planner'),
    path('api/budget-cart/', api_budget_cart, name='api_budget_cart'),
    path('api/add-bulk-to-cart/', api_add_bulk_to_cart, name='api_add_bulk_to_cart'),
    path('update-complaint-status/<int:complaint_id>/<str:status>/', update_complaint_status, name='update_complaint_status'),

    path('select-delivery-slot/<str:total>', select_delivery_slot, name='select_delivery_slot'),
    path('api/predict-eta/', predict_eta_api, name='predict_eta_api'),
    path('track-delivery/<int:order_id>/', track_delivery, name='track_delivery'),
    path('track-delivery-live/<int:order_id>/', track_delivery_live, name='track_delivery_live'),
    path('update-delivery-status/<int:delivery_id>/<str:status>/', update_delivery_status, name='update_delivery_status'),
    path('driver-update-status/<int:delivery_id>/<str:status>/', driver_update_status, name='driver_update_status'),
    path('notifications/', customer_notifications, name='customer_notifications'),
    path('api/delivery-status/<int:order_id>/', api_delivery_status, name='api_delivery_status'),
    path('api/update-location/', update_agent_location, name='update_agent_location'),
    path('api/agent-location/<int:order_id>/', api_agent_location, name='api_agent_location'),
    path('admin/delivery-dashboard/', admin_delivery_dashboard, name='admin_delivery_dashboard'),
    path('admin/reassign-delivery/<int:delivery_id>/', admin_reassign_delivery, name='admin_reassign_delivery'),

    path('my-pantry/', my_smart_pantry, name='my_smart_pantry'),
    path('api/add-to-pantry/', api_add_to_pantry, name='api_add_to_pantry'),
    path('api/check-low-stock/', api_check_low_stock, name='api_check_low_stock'),
    path('api/get-pantry/', api_get_pantry, name='api_get_pantry'),

    path('price-comparison/<int:product_id>/', product_price_details, name='product_price_details'),
    path('compare-prices/<int:product_id>/', api_product_price_comparison, name='compare_prices_v2'),
    path('suggest-alternatives/<int:product_id>/', api_alternative_products, name='suggest_alternatives_v2'),
    path('api/top-deals/', api_discounted_products, name='api_top_deals'),

    path("deliverindex/",deliveryindex,name="delivery_index"),
    path("delivery/profile/", delivery_profile, name="delivery_profile"),
    path("accept_order/<int:order_id>",accept_order,name="accept_order"),
    path("delivery/assigned-orders/", assigned_orders, name="assigned_orders"),
    path("delivery/verify-otp/<int:order_id>/",verify_delivery_otp, name="verify_delivery_otp"),
    path('approve-delivery/<int:id>/', approve_delivery, name='approve_delivery'),
    path('api/suggestions/', api_suggestions, name='api_suggestions'),
    path('api/trending/', api_trending, name='api_trending'),
    path('products/', products_page, name='products_page'),
    path('filter-products/', filter_products_api, name='filter_products_api'),

    path('add-review/', add_review, name='add_review'),
    path('product-reviews/<int:product_id>/', get_product_reviews, name='get_product_reviews'),
    path('average-rating/<int:product_id>/', get_average_rating, name='get_average_rating'),
    path('daily-sales-report/', admin_daily_sales_report, name='admin_daily_sales_report'),
    path('seller-sales-report/<int:seller_id>/', seller_sales_report, name='seller_sales_report'),
    path('api/generate-seller-report/', api_generate_seller_report, name='api_generate_seller_report'),
    path('admin-intel/delivery-report/', admin_delivery_report, name='admin_delivery_report'),
    path('api/delivery-report/', api_delivery_report, name='api_delivery_report'),

    path('seasonal-packs/', seasonal_packs, name='seasonal_packs'),
    path('add-pack-to-cart/<int:pack_id>/', add_pack_to_cart, name='add_pack_to_cart'),
    path('family-groups/', family_group_manage, name='family_group_manage'),
]



