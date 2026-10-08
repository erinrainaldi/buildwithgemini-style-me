#!/usr/bin/env python3
"""Batch ingest and auto-catalog images from Google Cloud Storage into the Style-Me closet.

Inspects all images in `gs://style-me-closet-130f91/` (or a specified prefix), checks which
ones are not yet cataloged in Firestore, runs Gemini Multimodal Vision (`gemini-2.5-flash`)
to analyze the clothing piece (item name, category, color, material, pattern, occasions, tags),
and registers the item in Firestore so it immediately appears in your closet and is available
to your AI Stylist agent.

Usage:
    python sync_gcs_closet.py
    python sync_gcs_closet.py --prefix uploads/
    python sync_gcs_closet.py --dry-run
"""

import argparse
import json
import os
import sys
import uuid
from typing import Any, Dict, List, Set

from google import genai
from google.genai import types
from google.cloud import firestore, storage

PROJECT_ID = os.getenv("PROJECT_ID", "qwiklabs-gcp-04-a9587ec200a7")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "style-me-closet-130f91")
COLLECTION_NAME = "wardrobe_items"

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}


def get_existing_image_urls(db: firestore.Client) -> Set[str]:
    """Return a set of all image_urls already stored in Firestore."""
    docs = db.collection(COLLECTION_NAME).stream()
    urls = set()
    for doc in docs:
        d = doc.to_dict()
        url = d.get("image_url", "").strip()
        if url:
            urls.add(url)
    return urls


def analyze_clothing_image(client: genai.Client, image_bytes: bytes, mime_type: str) -> Dict[str, Any]:
    """Call Gemini multimodal model to extract fashion metadata from the image."""
    prompt = """You are a fashion cataloging expert. Analyze this image of a clothing or accessory piece.
Extract structured metadata for a personal wardrobe database.

Return ONLY a valid JSON object matching this schema with no extra text or markdown formatting:
{
  "name": "Concise descriptive piece title, e.g. Silk Ivory Camisole Blouse or Charcoal Tailored Blazer",
  "category": "One of: dresses, tops, bottoms, jackets, shoes, accessories",
  "subcategory": "Granular type e.g. blazer, slip dress, trousers, heels, handbag, sweater",
  "color": "Dominant color e.g. navy, emerald green, ivory, black, camel",
  "material": "Estimated primary material e.g. silk, wool, cotton, leather, denim, linen",
  "pattern": "e.g. solid, striped, floral, plaid, houndstooth",
  "occasions": ["e.g. work", "date night", "casual", "formal"],
  "tags": ["e.g. minimalist", "quiet luxury", "tailored", "breathable", "vintage"]
}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )

    try:
        return json.loads(response.text)
    except Exception as e:
        print(f"  Warning: JSON parsing failed ({e}), raw output: {response.text}")
        return {
            "name": "Wardrobe Piece",
            "category": "tops",
            "subcategory": "top",
            "color": "neutral",
            "material": "fabric",
            "pattern": "solid",
            "occasions": ["casual"],
            "tags": ["wardrobe"],
        }


def main():
    parser = argparse.ArgumentParser(description="Sync images from GCS into the Style-Me closet using Gemini Vision.")
    parser.add_argument("--bucket", default=GCS_BUCKET_NAME, help="GCS bucket name")
    parser.add_argument("--prefix", default="", help="Optional subfolder prefix inside the bucket")
    parser.add_argument("--dry-run", action="store_true", help="Analyze images without writing to Firestore")
    args = parser.parse_args()

    print(f"📦 Connecting to Cloud Storage bucket: gs://{args.bucket}/ (prefix: '{args.prefix}')")
    storage_client = storage.Client(project=PROJECT_ID)
    bucket = storage_client.bucket(args.bucket)

    print(f"🗄️ Connecting to Firestore database (project: {PROJECT_ID})...")
    db = firestore.Client(project=PROJECT_ID)

    existing_urls = get_existing_image_urls(db)
    print(f"ℹ️ Found {len(existing_urls)} existing items in the closet database.\n")

    blobs = list(bucket.list_blobs(prefix=args.prefix))
    # Exclude assembled outfit generations (e.g. outfit_*.jpg) unless requested
    image_blobs = [
        b for b in blobs 
        if any(b.name.lower().endswith(ext) for ext in VALID_EXTENSIONS)
        and not b.name.startswith("outfit_")
    ]

    if not image_blobs:
        print("No individual clothing image files found to index in bucket.")
        return

    print(f"🔍 Found {len(image_blobs)} total image files in bucket.")
    unindexed = []
    for b in image_blobs:
        public_url = f"https://storage.googleapis.com/{args.bucket}/{b.name}"
        if public_url not in existing_urls:
            unindexed.append(b)

    print(f"✨ Found {len(unindexed)} new/unindexed images to catalog.\n")
    if not unindexed:
        print("✅ All bucket images are already registered in your closet!")
        return

    gemini_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")

    for i, blob in enumerate(unindexed, 1):
        public_url = f"https://storage.googleapis.com/{args.bucket}/{blob.name}"
        print(f"[{i}/{len(unindexed)}] Analyzing gs://{args.bucket}/{blob.name} with Gemini Vision...")

        try:
            # Download image bytes
            image_bytes = blob.download_as_bytes()
            mime_type = blob.content_type or "image/jpeg"
            if not mime_type or mime_type == "application/octet-stream":
                ext = blob.name.lower().split(".")[-1]
                mime_type = f"image/{ext}" if ext != "jpg" else "image/jpeg"

            # Run Gemini Vision analysis
            meta = analyze_clothing_image(gemini_client, image_bytes, mime_type)

            cat = meta.get("category", "tops").lower()
            item_id = f"item_{cat}_{uuid.uuid4().hex[:8]}"

            item_data = {
                "id": item_id,
                "name": meta.get("name", blob.name),
                "category": cat,
                "subcategory": meta.get("subcategory", cat).lower(),
                "color": meta.get("color", "").lower(),
                "material": meta.get("material", "").lower(),
                "pattern": meta.get("pattern", "solid").lower(),
                "tags": [t.lower() for t in meta.get("tags", [])],
                "occasions": [o.lower() for o in meta.get("occasions", [])],
                "season": "all-season",
                "brand": "Direct Upload",
                "image_url": public_url,
                "source_url": f"gs://{args.bucket}/{blob.name}",
            }

            print(f"  ✓ Identified: {item_data['name']}")
            print(f"    Category: {item_data['category']} | Color: {item_data['color']} | Material: {item_data['material']}")
            print(f"    Occasions: {', '.join(item_data['occasions'])}")

            if not args.dry_run:
                db.collection(COLLECTION_NAME).document(item_id).set(item_data)
                print(f"  ✓ Saved to Firestore (ID: {item_id})\n")
            else:
                print(f"  [Dry Run] Skipped Firestore write.\n")

        except Exception as err:
            print(f"  ❌ Error processing {blob.name}: {err}\n")

    print(f"🎉 Done! Processed {len(unindexed)} images.")
    if not args.dry_run:
        print("All pieces are now live in your closet and ready for your AI Stylist.")


if __name__ == "__main__":
    main()
