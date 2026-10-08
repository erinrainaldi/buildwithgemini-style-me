"""Seed script to populate initial virtual closet wardrobe items in Firestore."""

from google.cloud import firestore

PROJECT_ID = "qwiklabs-gcp-04-a9587ec200a7"
COLLECTION_NAME = "wardrobe_items"

SAMPLE_ITEMS = [
    {
        "id": "item_top_001",
        "name": "Classic White Linen Button-Down",
        "category": "tops",
        "subcategory": "shirt",
        "color": "white",
        "material": "linen",
        "pattern": "solid",
        "tags": ["casual", "work", "breathable", "minimalist", "summer"],
        "season": "spring/summer",
        "occasions": ["work", "casual", "brunch"],
        "brand": "Uniqlo",
        "image_url": "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=600",
    },
    {
        "id": "item_top_002",
        "name": "Black Silk Camisole",
        "category": "tops",
        "subcategory": "tank",
        "color": "black",
        "material": "silk",
        "pattern": "solid",
        "tags": ["dressy", "night out", "date night", "layering", "chic"],
        "season": "all-season",
        "occasions": ["date night", "party", "dinner"],
        "brand": "Cuyana",
        "image_url": "https://images.unsplash.com/photo-1503342217505-b0a15ec3261c?w=600",
    },
    {
        "id": "item_bottom_001",
        "name": "High-Waist Straight Leg Denim Jeans",
        "category": "bottoms",
        "subcategory": "jeans",
        "color": "medium blue",
        "material": "denim",
        "pattern": "solid",
        "tags": ["staple", "everyday", "vintage wash", "casual"],
        "season": "all-season",
        "occasions": ["casual", "weekend", "brunch"],
        "brand": "Levi's",
        "image_url": "https://images.unsplash.com/photo-1541099649105-f69ad21f3246?w=600",
    },
    {
        "id": "item_bottom_002",
        "name": "Tailored Beige Pleated Trousers",
        "category": "bottoms",
        "subcategory": "trousers",
        "color": "beige",
        "material": "wool blend",
        "pattern": "solid",
        "tags": ["work", "business casual", "tailored", "smart", "quiet luxury"],
        "season": "all-season",
        "occasions": ["work", "dinner", "business casual"],
        "brand": "Cos",
        "image_url": "https://images.unsplash.com/photo-1594633312681-425c7b97ccd1?w=600",
    },
    {
        "id": "item_dress_001",
        "name": "Emerald Green Slip Midi Dress",
        "category": "dresses",
        "subcategory": "midi dress",
        "color": "emerald green",
        "material": "satin",
        "pattern": "solid",
        "tags": ["elegant", "date night", "cocktail", "glam"],
        "season": "all-season",
        "occasions": ["date night", "wedding guest", "cocktail party"],
        "brand": "Reformation",
        "image_url": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=600",
    },
    {
        "id": "item_jacket_001",
        "name": "Oversized Charcoal Wool Blazer",
        "category": "jackets",
        "subcategory": "blazer",
        "color": "charcoal grey",
        "material": "wool",
        "pattern": "herringbone",
        "tags": ["work", "layering", "structured", "chic", "fall/winter"],
        "season": "fall/winter",
        "occasions": ["work", "date night", "dinner", "business casual"],
        "brand": "Everlane",
        "image_url": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=600",
    },
    {
        "id": "item_jacket_002",
        "name": "Vintage Leather Moto Jacket",
        "category": "jackets",
        "subcategory": "moto jacket",
        "color": "black",
        "material": "leather",
        "pattern": "solid",
        "tags": ["edgy", "casual", "night out", "streetwear"],
        "season": "spring/fall",
        "occasions": ["casual", "date night", "concert"],
        "brand": "AllSaints",
        "image_url": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=600",
    },
    {
        "id": "item_shoe_001",
        "name": "Pointed-Toe Black Leather Ankle Boots",
        "category": "shoes",
        "subcategory": "boots",
        "color": "black",
        "material": "leather",
        "pattern": "solid",
        "tags": ["versatile", "capsule", "chic", "block heel"],
        "season": "fall/winter/spring",
        "occasions": ["work", "date night", "dinner", "casual"],
        "brand": "Vagabond",
        "image_url": "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=600",
    },
    {
        "id": "item_shoe_002",
        "name": "Clean White Minimalist Sneakers",
        "category": "shoes",
        "subcategory": "sneakers",
        "color": "white",
        "material": "leather",
        "pattern": "solid",
        "tags": ["casual", "comfortable", "everyday", "sporty"],
        "season": "all-season",
        "occasions": ["casual", "travel", "weekend"],
        "brand": "Veja",
        "image_url": "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=600",
    },
    {
        "id": "item_acc_001",
        "name": "Gold Chunky Chain Necklace",
        "category": "accessories",
        "subcategory": "jewelry",
        "color": "gold",
        "material": "brass",
        "pattern": "chain",
        "tags": ["statement", "layering", "accent", "date night"],
        "season": "all-season",
        "occasions": ["date night", "dinner", "work", "party"],
        "brand": "Mejuri",
        "image_url": "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=600",
    },
]


def seed_closet():
    print(f"Connecting to Firestore with project: {PROJECT_ID}...")
    db = firestore.Client(project=PROJECT_ID)
    collection_ref = db.collection(COLLECTION_NAME)

    for item in SAMPLE_ITEMS:
        doc_id = item["id"]
        collection_ref.document(doc_id).set(item)
        print(f"  ✓ Added {item['name']} ({item['category']}) -> id: {doc_id}")

    print(f"Successfully seeded {len(SAMPLE_ITEMS)} items to Firestore collection '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    seed_closet()
