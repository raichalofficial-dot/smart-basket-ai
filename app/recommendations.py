import pandas as pd
import numpy as np
try:
    from surprise import Dataset, Reader, SVD
    SURPRISE_AVAILABLE = True
except Exception:
    SURPRISE_AVAILABLE = False
try:
    from mlxtend.frequent_patterns import apriori, association_rules
    MLXTEND_AVAILABLE = True
except Exception:
    MLXTEND_AVAILABLE = False
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum
from .models import OrderItem, Product, BrowsingHistory, Order

def get_trending_products(limit=5):
    last_week = timezone.now() - timedelta(days=7)
    trending = OrderItem.objects.filter(order__created_at__gte=last_week) \
        .values('product_id', 'product__name') \
        .annotate(total_qty=Sum('quantity')) \
        .order_by('-total_qty')[:limit]
    
    if not trending:
        trending = OrderItem.objects.values('product_id', 'product__name') \
            .annotate(total_qty=Sum('quantity')) \
            .order_by('-total_qty')[:limit]
            
    products = []
    for t in trending:
        try:
            p = Product.objects.get(id=t['product_id'])
            products.append({
                'id': p.id,
                'name': p.name,
                'price': str(p.price),
                'selling_price': str(p.price - (p.price * p.discount / 100)),
                'discount': float(p.discount),
                'image': p.images.first().image.url if p.images.exists() else None
            })
        except Product.DoesNotExist:
            continue
    return products

def get_related_products(product_id, limit=5):
    try:
        Product.objects.get(id=product_id)
    except Product.DoesNotExist:
        return []
    
    all_products = list(Product.objects.all())
    if len(all_products) <= 1:
        return []
        
    texts = [f"{p.category.CategoryName} {p.brand.brandName} {p.name}" for p in all_products]
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(texts)
    
    cosine_sim = cosine_similarity(tfidf_matrix, tfidf_matrix)
    
    base_idx = next(i for i, p in enumerate(all_products) if p.id == product_id)
    
    sim_scores = list(enumerate(cosine_sim[base_idx]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
    
    related_products = []
    for i, score in sim_scores[1:]:
        if len(related_products) >= limit:
            break
        p = all_products[i]
        related_products.append({
            'id': p.id,
            'name': p.name,
            'price': str(p.price),
            'selling_price': str(p.price - (p.price * p.discount / 100)),
            'discount': float(p.discount),
            'image': p.images.first().image.url if p.images.exists() else None
        })
    return related_products

def get_frequently_bought_together(product_id, limit=3):
    orders = Order.objects.prefetch_related('items').all()
    transactions = []
    for order in orders:
        items = [item.product_id for item in order.items.all()]
        if len(items) > 1:
            transactions.append(items)
            
    if not transactions or not MLXTEND_AVAILABLE:
        return []
        
    from mlxtend.preprocessing import TransactionEncoder
    te = TransactionEncoder()
    te_ary = te.fit(transactions).transform(transactions)
    df = pd.DataFrame(te_ary, columns=te.columns_)
    
    frequent_itemsets = apriori(df, min_support=0.01, use_colnames=True)
    
    if frequent_itemsets.empty:
        return []
        
    rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=0.01)
    
    if rules.empty:
        return []
        
    consequents = set()
    for _, row in rules.iterrows():
        if product_id in row['antecedents']:
            consequents.update(row['consequents'])
            
    related_products = []
    for cid in consequents:
        if len(related_products) >= limit:
            break
        if cid != product_id:
            try:
                p = Product.objects.get(id=cid)
                related_products.append({
                    'id': p.id,
                    'name': p.name,
                    'price': str(p.price),
                    'selling_price': str(p.price - (p.price * p.discount / 100)),
                    'discount': float(p.discount),
                    'image': p.images.first().image.url if p.images.exists() else None
                })
            except Product.DoesNotExist:
                continue
    return related_products

def get_personalized_recommendations(user_id, limit=6):
    interactions = []
    
    orders = OrderItem.objects.filter(order__user_id__isnull=False)
    for o in orders:
        interactions.append({'user': o.order.user_id, 'item': o.product_id, 'rating': 5})
        
    browsing = BrowsingHistory.objects.all()
    for b in browsing:
        interactions.append({'user': b.user_id, 'item': b.product_id, 'rating': 2})
        
    if not interactions or not SURPRISE_AVAILABLE:
        return get_trending_products(limit)
        
    df = pd.DataFrame(interactions)
    df = df.groupby(['user', 'item']).rating.mean().reset_index()
    
    reader = Reader(rating_scale=(1, 5))
    data = Dataset.load_from_df(df[['user', 'item', 'rating']], reader)
    trainset = data.build_full_trainset()
    
    try:
        trainset.to_inner_uid(user_id)
        is_known = True
    except ValueError:
        is_known = False
        
    if not is_known:
        return get_trending_products(limit)
        
    algo = SVD()
    algo.fit(trainset)
    
    all_products = Product.objects.all()
    predictions = []
    for p in all_products:
        pred = algo.predict(user_id, p.id)
        predictions.append((p, pred.est))
        
    predictions.sort(key=lambda x: x[1], reverse=True)
    
    recs = []
    for p, score in predictions[:limit]:
        recs.append({
            'id': p.id,
            'name': p.name,
            'price': str(p.price),
            'selling_price': str(p.price - (p.price * p.discount / 100)),
            'discount': float(p.discount),
            'image': p.images.first().image.url if p.images.exists() else None
        })
    return recs
