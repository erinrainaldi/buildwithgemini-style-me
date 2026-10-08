"""FastAPI server providing both the chat interface and dedicated closet management endpoints."""

import os
import uuid
from typing import Any, Dict, List, Optional

import google.auth
import google.auth.transport.requests
import httpx
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from google.cloud import firestore, storage

# Pinned GCP Project & Config
PROJECT_ID = "qwiklabs-gcp-04-a9587ec200a7"
COLLECTION_NAME = "wardrobe_items"
GCS_BUCKET_NAME = "style-me-closet-130f91"

RESOURCE = os.environ.get("AGENT_ENGINE_RESOURCE_NAME", "")
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")

def _get_firestore_client() -> firestore.Client:
    return firestore.Client(project=PROJECT_ID)

def _get_storage_client() -> storage.Client:
    return storage.Client(project=PROJECT_ID)

app = FastAPI(title="style-me closet & chat assistant")

# --- Closet API Endpoints ---

@app.get("/api/items")
async def get_items(category: Optional[str] = None):
    """Retrieve all wardrobe items from Firestore."""
    try:
        db = _get_firestore_client()
        docs = db.collection(COLLECTION_NAME).stream()
        items = []
        for d in docs:
            it = d.to_dict()
            it["id"] = d.id
            if category and it.get("category", "").lower() != category.lower().strip():
                continue
            items.append(it)
        return JSONResponse({"status": "success", "items": items})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.post("/api/items/upload")
async def upload_item(
    name: str = Form(...),
    category: str = Form(...),
    color: str = Form(...),
    material: str = Form(...),
    brand: str = Form(""),
    occasions: str = Form("casual"),
    tags: str = Form(""),
    image: Optional[UploadFile] = File(None),
):
    """Upload a new wardrobe item with optional image directly to GCS and Firestore."""
    try:
        image_url = ""
        if image and image.filename:
            content_type = image.content_type or "image/jpeg"
            ext = image.filename.split(".")[-1] if "." in image.filename else "jpg"
            unique_name = f"item_{category.lower()}_{uuid.uuid4().hex[:8]}.{ext}"

            contents = await image.read()
            storage_client = _get_storage_client()
            bucket = storage_client.bucket(GCS_BUCKET_NAME)
            blob = bucket.blob(unique_name)
            blob.upload_from_string(contents, content_type=content_type)
            image_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{unique_name}"

        item_id = f"item_{category.lower()}_{uuid.uuid4().hex[:8]}"
        occ_list = [o.strip().lower() for o in occasions.split(",") if o.strip()]
        tag_list = [t.strip().lower() for t in tags.split(",") if t.strip()]

        item_data = {
            "id": item_id,
            "name": name.strip(),
            "category": category.strip().lower(),
            "subcategory": category.strip().lower(),
            "color": color.strip().lower(),
            "material": material.strip().lower(),
            "pattern": "solid",
            "tags": tag_list,
            "occasions": occ_list or ["casual"],
            "season": "all-season",
            "brand": brand.strip(),
            "image_url": image_url,
        }

        db = _get_firestore_client()
        db.collection(COLLECTION_NAME).document(item_id).set(item_data)
        return JSONResponse({"status": "success", "item": item_data})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@app.delete("/api/items/{item_id}")
async def delete_item(item_id: str):
    """Remove an item from Firestore and remove image from Cloud Storage if stored there."""
    try:
        db = _get_firestore_client()
        doc_ref = db.collection(COLLECTION_NAME).document(item_id)
        doc = doc_ref.get()
        if not doc.exists:
            return JSONResponse(status_code=404, content={"status": "error", "message": "Item not found"})

        data = doc.to_dict()
        doc_ref.delete()

        img_url = data.get("image_url", "")
        if GCS_BUCKET_NAME in img_url:
            try:
                fname = img_url.split(f"{GCS_BUCKET_NAME}/")[-1].split("?")[0]
                if fname:
                    storage_client = _get_storage_client()
                    storage_client.bucket(GCS_BUCKET_NAME).blob(fname).delete()
            except Exception:
                pass

        return JSONResponse({"status": "success", "message": f"Deleted {data.get('name')}"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


# --- Chat & A2A Passthrough (When deployed to Agent Runtime) ---

_A2UI_MIME = "application/json+a2ui"
_contexts: dict[str, str] = {}

def _extract_parts(parts: list) -> list[dict]:
    out: list[dict] = []
    for p in parts:
        root = getattr(p, "root", p)
        text = getattr(root, "text", None)
        if text:
            out.append({"kind": "text", "text": text})
            continue

        data = getattr(root, "data", None)
        if data is not None:
            # Handle nested dictionary if wrapped
            if isinstance(data, dict) and "data" in data and "metadata" in data:
                meta = data.get("metadata") or {}
                mime = meta.get("mimeType")
                if mime == _A2UI_MIME:
                    out.append({"kind": "a2ui", "data": data.get("data")})
                    continue
            meta = getattr(root, "metadata", None) or {}
            mime = meta.get("mimeType") if isinstance(meta, dict) else None
            if mime == _A2UI_MIME:
                out.append({"kind": "a2ui", "data": data})
                continue

        uri = getattr(getattr(root, "file", None), "uri", None)
        if uri:
            out.append({"kind": "text", "text": uri})
    return out


@app.post("/chat")
async def chat(req: Request):
    if not RESOURCE:
        return JSONResponse({
            "parts": [
                {
                    "kind": "text",
                    "text": "The agent backend is ready. For full conversation via /chat, run with AGENT_ENGINE_RESOURCE_NAME set, or use the interactive closet manager above!",
                }
            ]
        })

    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "web-user"
    parts: list[dict] = []

    try:
        from a2a.client import ClientConfig, ClientFactory
        from a2a.types import AgentCard, Message, Part, Role, TaskArtifactUpdateEvent, TextPart, TransportProtocol

        location = RESOURCE.split("/locations/")[1].split("/")[0]
        a2a_base = f"https://{location}-aiplatform.googleapis.com/reasoningEngines/v1/{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
        a2a_card_url = f"{a2a_base}/.well-known/agent-card.json"

        creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        creds.refresh(google.auth.transport.requests.Request())
        headers = {"Authorization": f"Bearer {creds.token}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(headers=headers, timeout=120) as client:
            resp = await client.get(a2a_card_url)
            resp.raise_for_status()
            card = AgentCard(**resp.json())
            card.url = a2a_base

            factory = ClientFactory(
                ClientConfig(
                    supported_transports=[TransportProtocol.jsonrpc, TransportProtocol.http_json],
                    httpx_client=client,
                )
            )
            a2a_client = factory.create(card)
            msg = Message(
                message_id=str(uuid.uuid4()),
                role=Role.user,
                parts=[Part(root=TextPart(text=message))],
                context_id=_contexts.get(user_id),
            )

            last_task = None
            got_artifact_update = False
            async for event in a2a_client.send_message(msg):
                if isinstance(event, Message):
                    parts.extend(_extract_parts(event.parts))
                    continue
                if not isinstance(event, tuple):
                    continue
                task, update = event
                if task is not None:
                    last_task = task
                    if getattr(task, "context_id", None):
                        _contexts[user_id] = task.context_id
                if isinstance(update, Message):
                    parts.extend(_extract_parts(update.parts))
                elif isinstance(update, TaskArtifactUpdateEvent):
                    got_artifact_update = True
                    parts.extend(_extract_parts(update.artifact.parts))

            if not parts and last_task is not None:
                for item in getattr(last_task, "history", None) or []:
                    if isinstance(item, Message) and getattr(item, "role", None) == Role.agent:
                        parts.extend(_extract_parts(item.parts))
                if not parts:
                    for artifact in getattr(last_task, "artifacts", None) or []:
                        parts.extend(_extract_parts(artifact.parts))
    except Exception as e:
        parts.append({"kind": "text", "text": f"Error: {e}"})

    if not parts:
        parts = [{"kind": "text", "text": "(The agent didn't return a reply.)"}]
    return JSONResponse({"parts": parts})


# Static frontend files
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
app.mount('/', StaticFiles(directory=STATIC_DIR, html=True), name='static')

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
