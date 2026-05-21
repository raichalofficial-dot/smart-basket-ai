from app.models import Product, SeasonalPack
import random

def populate_packs():
    all_products = list(Product.objects.all())
    if len(all_products) < 5:
        print("Not enough products to create packs.")
        return

    # Pack 1: Onam Celebration Pack
    onam_pack, created = SeasonalPack.objects.get_or_create(
        name="Onam Grand Celebration Pack",
        description="Everything you need for a traditional Onam Sadhya. Includes rice, jaggery, banana chips, and more!",
        festival_name="Onam",
        discount_percentage=15.0
    )
    if created:
        onam_pack.products.set(random.sample(all_products, 5))
    
    # Pack 2: Weekend Brunch Bundle
    brunch_pack, created = SeasonalPack.objects.get_or_create(
        name="Healthy Morning Bundle",
        description="Fresh fruits, oats, local honey, and milk for the perfect healthy start to your weekend.",
        festival_name="Weekend Deals",
        discount_percentage=10.0
    )
    if created:
        brunch_pack.products.set(random.sample(all_products, 4))

    print("Created seasonal packs successfully!")

if __name__ == "__main__":
    populate_packs()
