# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import urllib.parse
import urllib.request
import uuid
from typing import Any, Dict, List, Optional

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.memory import VertexAiMemoryBankService
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import types

from .a2ui_utils import a2ui_callback

# Hardcoded project ID & bucket required for Agent Platform compatibility
PROJECT_ID = "qwiklabs-gcp-04-a9587ec200a7"
LOCATION = "us-central1"
MEMORY_BANK_ID = "1050693586380652544"
COLLECTION_NAME = "wardrobe_items"
GCS_BUCKET_NAME = "style-me-closet-130f91"

MODEL = "gemini-3.6-flash"


def memory_bank_service_builder() -> VertexAiMemoryBankService:
    """Build the Vertex AI Memory Bank service for deployment and runtime."""
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location=LOCATION,
        agent_engine_id=MEMORY_BANK_ID,
    )


async def generate_memories_callback(callback_context: CallbackContext):
    """After each turn, extract durable facts and user preferences to Memory Bank."""
    await callback_context.add_session_to_memory()
    return None


def _get_firestore_client() -> firestore.Client:
    """Return a Firestore client pinned to the explicit project ID."""
    return firestore.Client(project=PROJECT_ID)


def _get_storage_client() -> storage.Client:
    """Return a Cloud Storage client pinned to the explicit project ID."""
    return storage.Client(project=PROJECT_ID)


def list_wardrobe_items(
    category: Optional[str] = None,
    color: Optional[str] = None,
    occasion: Optional[str] = None,
    tag: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List or search items in the user's virtual closet.

    Args:
        category: Optional category filter, e.g. 'tops', 'bottoms', 'dresses', 'jackets', 'shoes', 'accessories'.
        color: Optional color substring match, e.g. 'white', 'black', 'blue', 'beige'.
        occasion: Optional occasion filter, e.g. 'work', 'date night', 'casual', 'party', 'dinner'.
        tag: Optional tag filter, e.g. 'minimalist', 'tailored', 'silk', 'summer'.

    Returns:
        A list of matching clothing/accessory items currently stored in the wardrobe.
    """
    db = _get_firestore_client()
    docs = db.collection(COLLECTION_NAME).stream()

    results: List[Dict[str, Any]] = []
    for doc in docs:
        item = doc.to_dict()
        item["id"] = doc.id

        if category and item.get("category", "").lower() != category.strip().lower():
            continue

        if color and color.strip().lower() not in item.get("color", "").lower():
            continue

        if occasion:
            target_occ = occasion.strip().lower()
            item_occs = [o.lower() for o in item.get("occasions", [])]
            if not any(target_occ in o for o in item_occs):
                continue

        if tag:
            target_tag = tag.strip().lower()
            item_tags = [t.lower() for t in item.get("tags", [])]
            if not any(target_tag in t for t in item_tags):
                continue

        results.append(item)

    return results


def add_wardrobe_item(
    name: str,
    category: str,
    color: str,
    material: str,
    pattern: str = "solid",
    subcategory: str = "",
    tags: Optional[List[str]] = None,
    occasions: Optional[List[str]] = None,
    season: str = "all-season",
    brand: str = "",
    image_url: str = "",
) -> Dict[str, Any]:
    """Add a new clothing or accessory item to the virtual closet.

    Args:
        name: Name or description of the clothing item, e.g. 'Silk Navy Midi Skirt'.
        category: Item category ('tops', 'bottoms', 'dresses', 'jackets', 'shoes', 'accessories').
        color: Dominant color, e.g. 'navy', 'cream', 'black'.
        material: Primary material/fabric, e.g. 'silk', 'cotton', 'denim', 'leather', 'wool'.
        pattern: Pattern if any ('solid', 'striped', 'floral', 'plaid', etc.).
        subcategory: More granular type, e.g. 'blazer', 'jeans', 'boots', 't-shirt'.
        tags: Descriptive style or aesthetic tags, e.g. ['minimalist', 'quiet luxury', 'breathable'].
        occasions: Suitable occasions, e.g. ['work', 'date night', 'casual', 'formal'].
        season: Applicable seasons ('spring', 'summer', 'fall', 'winter', 'all-season').
        brand: Brand name if known, e.g. 'Everlane', 'Zara'.
        image_url: Optional image URL for the item.

    Returns:
        A dictionary with status and the newly created wardrobe item record.
    """
    db = _get_firestore_client()
    item_id = f"item_{category.lower()}_{uuid.uuid4().hex[:8]}"

    item_data = {
        "id": item_id,
        "name": name.strip(),
        "category": category.strip().lower(),
        "subcategory": subcategory.strip().lower() if subcategory else category.strip().lower(),
        "color": color.strip().lower(),
        "material": material.strip().lower(),
        "pattern": pattern.strip().lower(),
        "tags": [t.strip().lower() for t in (tags or [])],
        "occasions": [o.strip().lower() for o in (occasions or ["casual"])],
        "season": season.strip().lower(),
        "brand": brand.strip(),
        "image_url": image_url.strip(),
    }

    db.collection(COLLECTION_NAME).document(item_id).set(item_data)
    return {"status": "success", "message": f"Added '{name}' to wardrobe.", "item": item_data}


def remove_wardrobe_item(
    item_id: Optional[str] = None,
    item_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Remove or delete an item from the virtual closet by its item ID or name.

    Args:
        item_id: Exact ID of the item in Firestore (e.g. 'item_dress_001').
        item_name: Name or keyword of the item to delete if ID is unknown (e.g. 'floral summer wrap dress').

    Returns:
        A dictionary with deletion status and confirmation message.
    """
    db = _get_firestore_client()
    col = db.collection(COLLECTION_NAME)

    target_doc = None
    target_data = None

    if item_id:
        doc_ref = col.document(item_id.strip())
        doc = doc_ref.get()
        if doc.exists:
            target_doc = doc_ref
            target_data = doc.to_dict()
    elif item_name:
        needle = item_name.strip().lower()
        for doc in col.stream():
            d = doc.to_dict()
            if needle in d.get("name", "").lower():
                target_doc = col.document(doc.id)
                target_data = d
                break

    if not target_doc:
        return {
            "status": "error",
            "message": f"Item not found with identifier item_id='{item_id}' or item_name='{item_name}'.",
        }

    # Delete doc from Firestore
    target_doc.delete()

    # Clean up associated Cloud Storage image if it lives in the project bucket
    img_url = target_data.get("image_url", "")
    if GCS_BUCKET_NAME in img_url:
        try:
            filename = img_url.split(f"{GCS_BUCKET_NAME}/")[-1].split("?")[0]
            if filename:
                storage_client = _get_storage_client()
                storage_client.bucket(GCS_BUCKET_NAME).blob(filename).delete()
        except Exception:
            pass

    return {
        "status": "success",
        "message": f"Successfully removed '{target_data.get('name')}' (ID: {target_doc.id}) from the closet.",
        "removed_item": target_data,
    }


def get_weather_for_outfit(location: str) -> Dict[str, Any]:
    """Fetch current real-world weather conditions and temperature for styling decisions.

    Args:
        location: City or location name, e.g. 'New York', 'Paris', 'Tokyo', 'San Francisco'.

    Returns:
        A dictionary containing temperature (°F), feels-like temp, weather summary,
        precipitation, and styling tips based on the forecast.
    """
    try:
        encoded_loc = urllib.parse.quote(location.strip())
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={encoded_loc}&count=1&language=en&format=json"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "StyleMeAgent/1.0"})

        with urllib.request.urlopen(req, timeout=5) as resp:
            geo_data = json.loads(resp.read().decode())

        results = geo_data.get("results")
        if not results:
            return {
                "status": "error",
                "message": f"Could not find coordinates for location: '{location}'.",
                "location": location,
            }

        place = results[0]
        lat, lon = place["latitude"], place["longitude"]
        resolved_name = f"{place.get('name')}, {place.get('admin1', place.get('country', ''))}"

        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,apparent_temperature,precipitation,weather_code"
            f"&temperature_unit=fahrenheit"
        )
        req_w = urllib.request.Request(weather_url, headers={"User-Agent": "StyleMeAgent/1.0"})
        with urllib.request.urlopen(req_w, timeout=5) as resp_w:
            w_data = json.loads(resp_w.read().decode())

        current = w_data.get("current", {})
        temp_f = current.get("temperature_2m", 70.0)
        apparent_temp_f = current.get("apparent_temperature", temp_f)
        precip = current.get("precipitation", 0.0)
        code = current.get("weather_code", 0)

        if code == 0:
            condition = "Clear / Sunny"
        elif code in (1, 2, 3):
            condition = "Mainly clear to overcast"
        elif code in (45, 48):
            condition = "Foggy"
        elif code in (51, 53, 55, 61, 63, 65, 80, 81, 82):
            condition = "Rainy / Showers"
        elif code in (71, 73, 75, 85, 86):
            condition = "Snowy"
        elif code in (95, 96, 99):
            condition = "Thunderstorm"
        else:
            condition = "Partly Cloudy"

        styling_tips = []
        if precip > 0 or "Rain" in condition:
            styling_tips.append("Precipitation expected: recommend leather footwear over suede, and outerwear with coverage.")
        if apparent_temp_f < 50:
            styling_tips.append("Chilly/Cold: prioritize warm layers, wool blazers/coats, and closed-toe boots.")
        elif apparent_temp_f < 68:
            styling_tips.append("Mild/Brisk: ideal for chic layering — e.g., a camisole or button-down under an oversized blazer or moto jacket.")
        else:
            styling_tips.append("Warm/Balmy: recommend lightweight breathable fabrics like linen, silk, and comfortable sneakers or open footwear.")

        return {
            "status": "success",
            "location": resolved_name,
            "temperature_f": round(temp_f, 1),
            "feels_like_f": round(apparent_temp_f, 1),
            "condition": condition,
            "precipitation_inches": precip,
            "styling_weather_tips": styling_tips,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Weather fetch failed: {str(e)}",
            "location": location,
        }


def get_color_palette_advice(
    color_name_or_hex: str,
    scheme_mode: str = "analogic",
) -> Dict[str, Any]:
    """Fetch color harmony palettes and complementary shades using The Color API (public-apis).

    Args:
        color_name_or_hex: Color name or hex code (e.g. 'emerald green', '0047AB', 'beige', 'charcoal', 'navy').
        scheme_mode: Color scheme theory to apply: 'analogic', 'complement', 'triad', 'quad', 'monochrome'.

    Returns:
        A dictionary with the identified base color, complementary palette recommendations,
        and practical styling advice for combining these colors in an outfit.
    """
    COLOR_HEX_MAP = {
        "emerald green": "50C878",
        "emerald": "50C878",
        "forest green": "228B22",
        "navy": "000080",
        "navy blue": "000080",
        "charcoal": "36454F",
        "charcoal grey": "36454F",
        "beige": "F5F5DC",
        "camel": "C19A6B",
        "burgundy": "800020",
        "olive": "808000",
        "white": "FFFFFF",
        "black": "000000",
        "cream": "FFFDD0",
        "rust": "B7410E",
        "terracotta": "E2725B",
        "lavender": "E6E6FA",
        "cobalt": "0047AB",
    }

    clean_input = color_name_or_hex.strip().lower().lstrip("#")
    hex_code = COLOR_HEX_MAP.get(clean_input, clean_input)

    api_key = os.getenv("COLOR_API_KEY", "")

    try:
        url = f"https://www.thecolorapi.com/scheme?hex={hex_code}&mode={scheme_mode}&count=4"
        headers = {"User-Agent": "StyleMeAgent/1.0"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        seed_name = data.get("seed", {}).get("name", {}).get("value", color_name_or_hex)
        seed_hex = data.get("seed", {}).get("hex", {}).get("clean", hex_code)

        paired_colors = []
        for c in data.get("colors", []):
            paired_colors.append({
                "name": c.get("name", {}).get("value"),
                "hex": c.get("hex", {}).get("value"),
            })

        return {
            "status": "success",
            "base_color": seed_name,
            "base_hex": f"#{seed_hex}",
            "scheme_mode": scheme_mode,
            "harmonious_pairings": paired_colors,
            "styling_advice": (
                f"When building an outfit around {seed_name}, pair it with {scheme_mode} tones like "
                f"{', '.join([c['name'] for c in paired_colors[:2]])} for a balanced, intentional color palette."
            ),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to fetch color scheme: {str(e)}",
            "input_color": color_name_or_hex,
        }


def search_fashion_inspiration(
    query: str,
    limit: int = 3,
) -> Dict[str, Any]:
    """Search street-style and fashion photography for styling inspiration and moodboards.

    Args:
        query: Fashion search query (e.g., 'minimalist street style', 'date night slip dress', 'quiet luxury autumn').
        limit: Max number of photo results to return (default 3).

    Returns:
        A list of fashion inspiration photos with image URLs, descriptions, and photographer credits.
    """
    access_key = os.getenv("UNSPLASH_ACCESS_KEY", "").strip()

    if access_key:
        try:
            encoded_query = urllib.parse.quote(f"fashion {query}".strip())
            url = f"https://api.unsplash.com/search/photos?query={encoded_query}&per_page={limit}&orientation=portrait"
            headers = {
                "Authorization": f"Client-ID {access_key}",
                "User-Agent": "StyleMeAgent/1.0",
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())

            photos = []
            for item in data.get("results", [])[:limit]:
                photos.append({
                    "title": item.get("alt_description") or query,
                    "image_url": item.get("urls", {}).get("regular", ""),
                    "photographer": item.get("user", {}).get("name", "Unsplash Contributor"),
                })

            if photos:
                return {
                    "status": "success",
                    "source": "Unsplash API",
                    "query": query,
                    "photos": photos,
                }
        except Exception:
            pass

    EDITORIAL_INSPIRATION = [
        {
            "match": ["date", "night", "slip", "dress", "dinner", "evening", "cocktail"],
            "title": "Minimalist Silk Slip Dress Evening Look",
            "image_url": "https://images.unsplash.com/photo-1595777457583-95e059d581b8?w=800",
            "photographer": "Tamara Bellis",
            "aesthetic": "Chic Evening / Date Night",
        },
        {
            "match": ["work", "blazer", "office", "tailored", "trouser", "suit", "business"],
            "title": "Tailored Blazer & Trousers Power Dressing",
            "image_url": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=800",
            "photographer": "Alexander Grey",
            "aesthetic": "Modern Professional / Quiet Luxury",
        },
        {
            "match": ["leather", "moto", "jacket", "edgy", "boots", "concert", "rock"],
            "title": "Edgy Moto Leather Jacket & Ankle Boots",
            "image_url": "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=800",
            "photographer": "Ali Pazani",
            "aesthetic": "Urban Chic / Streetwear",
        },
        {
            "match": ["casual", "weekend", "denim", "sneakers", "linen", "brunch"],
            "title": "Linen Shirt, Classic Denim & Clean White Sneakers",
            "image_url": "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?w=800",
            "photographer": "Laura Chouette",
            "aesthetic": "Elevated Casual / Weekend Minimalist",
        },
    ]

    matched = []
    q_words = [w.lower() for w in query.split()]
    for entry in EDITORIAL_INSPIRATION:
        if any(keyword in q_words or any(keyword in w for w in q_words) for keyword in entry["match"]):
            matched.append({
                "title": entry["title"],
                "image_url": entry["image_url"],
                "photographer": entry["photographer"],
                "aesthetic": entry["aesthetic"],
            })

    if not matched:
        matched = [{
            "title": EDITORIAL_INSPIRATION[0]["title"],
            "image_url": EDITORIAL_INSPIRATION[0]["image_url"],
            "photographer": EDITORIAL_INSPIRATION[0]["photographer"],
            "aesthetic": EDITORIAL_INSPIRATION[0]["aesthetic"],
        }]

    return {
        "status": "success",
        "source": "Unsplash Curated Library",
        "query": query,
        "photos": matched[:limit],
    }


async def generate_outfit_image(
    item_ids: Optional[List[str]] = None,
    outfit_description: Optional[str] = None,
    tool_context: Optional[ToolContext] = None,
    save_to_storage: bool = False,
    save_as_artifact: bool = True,
) -> Dict[str, Any]:
    """Generate a high-fashion photo assembling the exact chosen wardrobe items into one cohesive outfit.

    Uses `gemini-3.1-flash-lite-image` in the global region. If `item_ids` are supplied, the tool
    fetches the exact items from the user's closet (name, color, material, pattern, subcategory)
    to ensure the generated image precisely showcases each individual piece picked out.

    Args:
        item_ids: Optional list of wardrobe item IDs from the user's closet to assemble in the photo
            (e.g., ['item_dress_001', 'item_jackets_002', 'item_shoes_003', 'item_accessories_004']).
        outfit_description: Optional manual or additional description of the outfit styling and pieces.
        tool_context: ToolContext provided by ADK for saving session artifacts.
        save_to_storage: Whether to upload and persist the image in the public Cloud Storage bucket.
            Defaults to False unless the user explicitly requested to save/store/keep it.
        save_as_artifact: Whether to register the image in the session's Artifacts panel.
            Defaults to True.

    Returns:
        A dictionary with image details, piece breakdown, artifact filename, and public URL if saved.
    """
    try:
        piece_descriptions = []
        fetched_items = []

        # 1. Fetch exact item records from Firestore if item_ids provided
        if item_ids:
            db = _get_firestore_client()
            for iid in item_ids:
                doc = db.collection(COLLECTION_NAME).document(iid.strip()).get()
                if doc.exists:
                    data = doc.to_dict()
                    name = data.get("name", "")
                    color = data.get("color", "")
                    material = data.get("material", "")
                    cat = data.get("category", "")
                    subcat = data.get("subcategory", cat)
                    pattern = data.get("pattern", "solid")
                    desc = f"a {color} {material} {subcat or name}"
                    if pattern and pattern != "solid":
                        desc += f" with {pattern} pattern"
                    piece_descriptions.append(f"{name} ({desc})")
                    fetched_items.append(data)

        # Build prompt that strictly enforces the presence of each individual item
        if piece_descriptions:
            items_list_str = "; ".join(piece_descriptions)
            items_instruction = (
                f"The image MUST clearly feature all of the following specific closet pieces arranged together as an assembled look: {items_list_str}. "
            )
            if outfit_description:
                items_instruction += f"Styling and vibe context: {outfit_description}. "
        elif outfit_description:
            items_instruction = f"The outfit must consist of these specific items: {outfit_description}. "
        else:
            return {
                "status": "error",
                "message": "Please provide either item_ids from the closet or an outfit_description.",
            }

        prompt = (
            "Professional studio flat-lay fashion photograph of a complete, coordinated outfit. "
            f"{items_instruction}"
            "Each clothing and accessory item listed above must be distinctly visible and neatly arranged together in one coordinated composition. "
            "Clean aesthetic, neutral linen background, high fashion magazine editorial styling, soft diffused studio lighting."
        )

        # 2. Call gemini-3.1-flash-lite-image
        client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        # Extract image bytes
        image_bytes = None
        mime_type = "image/jpeg"
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.data:
                    image_bytes = part.inline_data.data
                    mime_type = part.inline_data.mime_type or mime_type
                    break

        if not image_bytes:
            return {
                "status": "error",
                "message": "Image generation model did not return image bytes.",
            }

        unique_id = uuid.uuid4().hex[:8]
        filename = f"outfit_{unique_id}.jpg"

        # 3. Save as session artifact if tool_context available
        if save_as_artifact and tool_context:
            artifact_part = types.Part(
                inline_data=types.Blob(
                    data=image_bytes,
                    mime_type=mime_type,
                )
            )
            try:
                await tool_context.save_artifact(filename=filename, artifact=artifact_part)
            except Exception:
                pass

        # 4. Upload to Cloud Storage if save_to_storage=True
        public_url = ""
        if save_to_storage:
            storage_client = _get_storage_client()
            bucket = storage_client.bucket(GCS_BUCKET_NAME)
            blob = bucket.blob(filename)
            blob.upload_from_string(image_bytes, content_type=mime_type)
            public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"

        return {
            "status": "success",
            "pieces_included": [it.get("name") for it in fetched_items] or outfit_description,
            "saved_to_storage": save_to_storage,
            "public_image_url": public_url,
            "artifact_filename": filename if save_as_artifact else None,
            "message": (
                f"Generated outfit image containing all selected items and saved to Cloud Storage: {public_url}"
                if save_to_storage
                else "Generated outfit visual containing all selected items (preview)."
            ),
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to generate outfit image: {str(e)}",
        }


# Initialize A2UI Schema Manager (v0.8)
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are 'style-me', an expert AI Personal Stylist and Virtual Closet Assistant. "
        "Your mission is to help users make the best, most stylish use of the clothing and accessories already in their closet."
    ),
    workflow_description=(
        "1. Check weather when location or today/tonight is mentioned using `get_weather_for_outfit`.\n"
        "2. Check color harmony or pairing suggestions using `get_color_palette_advice` to justify color combinations.\n"
        "3. Look up street style visual inspiration using `search_fashion_inspiration` when users want visual styling ideas or moodboards.\n"
        "4. Query closet items with `list_wardrobe_items` and pick specific complementary pieces (dresses, tops, bottoms, jackets, shoes, accessories).\n"
        "5. Wardrobe Item Management: When the user asks to add or upload a new piece to their closet, use `add_wardrobe_item`. When the user asks to remove, delete, or discard an item, use `remove_wardrobe_item`.\n"
        "6. CRITICAL Outfit Image Generation: When the user asks to see an outfit or visualize pieces together, you MUST pass the exact `item_ids` of the individual pieces you picked from their closet (e.g. `item_ids=['item_dress_001', 'item_jacket_001', 'item_shoes_001']`) to `generate_outfit_image` so the generated image actually includes and reflects those specific items. Also include a rich `outfit_description` detailing the specific color, material, and styling of each piece.\n"
        "7. Image Persistence Choice: Only set `save_to_storage=True` in `generate_outfit_image` if the user explicitly asks to save, store, or keep the image in their permanent closet storage; otherwise default to `save_to_storage=False` for temporary previews.\n"
        "8. When presenting wardrobe pieces, curated outfit suggestions, or generated outfit visuals that have a public URL, return structured A2UI UI so they render as visual cards."
    ),
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include Image components, but only when you have a public https "
        "URL (for example the item's image_url from the wardrobe, or the public_image_url returned by generate_outfit_image when saved). "
        "Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the item instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    tools=[
        PreloadMemoryTool(),
        get_weather_for_outfit,
        get_color_palette_advice,
        search_fashion_inspiration,
        generate_outfit_image,
        list_wardrobe_items,
        add_wardrobe_item,
        remove_wardrobe_item,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
