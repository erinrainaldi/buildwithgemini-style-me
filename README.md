# Style-Me: Luxury AI Personal Stylist & Virtual Wardrobe

A multi-agent, visual personal stylist application built with the **Google Agent Development Kit (ADK)**, **Vertex AI Agent Engine (Reasoning Engine)**, **A2A Protocol**, and **Gemini 2.5/3.1** models.

Style-Me connects to a personal closet database in Google Cloud Firestore and helps users assemble coordinated outfits based on occasion, weather, color harmony, and personal taste. For every recommended look, it generates high-fashion visual previews styled on a sleek, headless female mannequin.

---

## 🌟 Key Features

1. **Virtual Closet Management**
   - **Interactive Grid**: Browse closet pieces with category filtering (`dresses`, `tops`, `bottoms`, `jackets`, `shoes`, `accessories`).
   - **Direct Image Upload**: Select files locally with instant thumbnail preview.
   - **Product Link Scraper**: Paste a URL from any store; the system parses OpenGraph, Twitter Cards, Schema.org JSON-LD, or microdata to extract the representative product image and caches it in Google Cloud Storage for permanent provenance.
   - **Provenance Badges**: Original source links are preserved and accessible directly on each closet piece card (`🔗 Source`).

2. **Automated Batch Ingestion (`sync_gcs_closet.py`)**
   - Upload hundreds of photos directly to Google Cloud Storage (`gs://<bucket>/`).
   - Run the ingestion CLI to auto-catalog all unindexed pieces with **Gemini Multimodal Vision (`gemini-2.5-flash`)**, extracting title, category, dominant color, material, pattern, occasion, and style tags into Firestore.

3. **Autonomous AI Stylist (`app/agent.py`)**
   - Built on Google ADK with ReAct agent loop and cross-session memory (`PreloadMemoryTool` + `Vertex AI Memory Bank`).
   - **Context-Aware Styling**: Checks real-time weather (`get_weather_for_outfit`), color wheel harmonies (`get_color_palette_advice`), and editorial street style inspirations (`search_fashion_inspiration`).
   - **Mandatory Mannequin Outfits**: For every recommended outfit, invokes `generate_outfit_image` using `gemini-3.1-flash-lite-image` to generate a high-fashion look styled on an upright, headless female mannequin.
   - **Saved Looks Prompting**: Automatically renders the look as an A2UI visual card and prompts the user whether they'd like to save the curated outfit to their permanent collection via `save_styled_look`.

4. **Modern Luxury Frontend**
   - Warm alabaster (`#f7f6f3`), obsidian (`#191c1f`), and champagne bronze (`#b38e5d`) editorial aesthetic with Playfair Display serif typography.
   - Native A2UI component renderer embedded inside a FastAPI async proxy.
   - Communicates with Vertex AI Agent Engine using the **A2A Protocol** (JSON-RPC over Server-Sent Events).

---

## 🏛️ Architecture & Project Structure

```
style-me/
├── app/                       # Core ADK Stylist Agent
│   ├── agent.py               # Stylist logic, mannequin image generation, tools & callbacks
│   ├── a2ui_utils.py          # A2UI v0.8 after_model_callback formatting
│   ├── memory_utils.py        # Vertex AI Memory Bank long-term memory callbacks
│   └── fast_api_app.py        # ADK API server
├── frontend/                  # Web Application & A2A Proxy (Cloud Run)
│   ├── main.py                # FastAPI proxy, product link scraper, GCS cache, and A2A event stream
│   ├── static/index.html      # Responsive luxury wardrobe manager & chat interface
│   ├── requirements.txt       # Frontend Python dependencies (FastAPI, httpx, bs4, firestore, etc.)
│   └── Dockerfile             # Container definition for Cloud Run deployment
├── sync_gcs_closet.py         # Batch GCS image ingestion & Gemini Vision auto-cataloger
├── pyproject.toml             # Agent dependencies (google-adk, a2ui-agent-sdk, etc.)
└── deployment_metadata.json   # Deployment tracking (Agent Runtime ID, target, timestamps)
```

---

## 📸 Batch Wardrobe Ingestion (`sync_gcs_closet.py`)

You can upload folders of clothing images directly to your Google Cloud Storage bucket and automatically catalog them into your closet using Gemini Multimodal Vision.

### Features
- **Delta Sync**: Only inspects and catalogs new images not yet registered in Firestore.
- **Multimodal AI Analysis (`gemini-2.5-flash`)**: Automatically identifies the item's name, category (`dresses`, `tops`, `bottoms`, `jackets`, `shoes`, `accessories`), dominant color, primary fabric/material, pattern, suitable occasions, and style tags.
- **Immediate Availability**: Newly cataloged items appear instantly in the wardrobe grid and are accessible to the AI Stylist agent.

### Step 1: Upload Images to Google Cloud Storage
Use the Google Cloud CLI to copy local photos directly to your bucket:

```bash
# Upload an entire directory of photos:
gcloud storage cp /path/to/my_clothes/* gs://style-me-closet-130f91/

# Or upload a specific subfolder:
gcloud storage cp -r /path/to/summer_capsule gs://style-me-closet-130f91/summer/
```

### Step 2: Run the Ingestion Script

```bash
# Preview what Gemini Vision detects without saving to the database:
python sync_gcs_closet.py --dry-run

# Run full sync and write items to Firestore:
python sync_gcs_closet.py

# Sync images from a specific folder prefix in the bucket:
python sync_gcs_closet.py --prefix summer/
```

#### CLI Options
| Flag | Description | Default |
|---|---|---|
| `--bucket` | Name of your GCS bucket | `style-me-closet-130f91` or `$GCS_BUCKET_NAME` |
| `--prefix` | Subfolder prefix to search inside the bucket | `""` (root of bucket) |
| `--dry-run` | Inspect & analyze images with Gemini without writing to Firestore | `False` |

---

## 🚀 Local Development

### Prerequisites
- Python 3.11+
- `uv`: [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
- `agents-cli`: `uv tool install google-agents-cli`
- Google Cloud SDK authenticated with Application Default Credentials:
  ```bash
  gcloud auth application-default login
  ```

### Run the ADK Agent Locally
```bash
uv sync
.venv/bin/adk web --port 8000 app
```
Navigate to `http://localhost:8000` to interact with the raw ADK agent and view A2UI execution graphs and artifacts.

### Run the Custom Frontend Locally
In a separate terminal:
```bash
cd frontend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

LOCAL_AGENT_URL="http://127.0.0.1:8000" \
AGENT_DIRECTORY="app" \
PORT=8080 \
python main.py
```
Open `http://localhost:8080` to experience the full luxury wardrobe application.

---

## ☁️ Deployment

### 1. Deploy Agent to Vertex AI Agent Engine
```bash
agents-cli deploy -d agent_runtime --region us-central1 --no-confirm-project
```
This updates the managed Reasoning Engine in Google Cloud (`us-central1`).

### 2. Deploy Frontend to Cloud Run
```bash
cd frontend
gcloud run deploy style-me-frontend \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars AGENT_ENGINE_RESOURCE_NAME="projects/735121233253/locations/us-central1/reasoningEngines/5594825610397483008",AGENT_DIRECTORY="app"
```

---

## 🔒 Environment & Configuration Reference

| Environment Variable | Description | Example / Default |
|---|---|---|
| `PROJECT_ID` | GCP Project ID | `qwiklabs-gcp-04-a9587ec200a7` |
| `GCS_BUCKET_NAME` | Bucket for closet and outfit images | `style-me-closet-130f91` |
| `AGENT_ENGINE_RESOURCE_NAME` | Vertex AI Reasoning Engine ID | `projects/.../reasoningEngines/5594825610397483008` |
| `PORT` | Web server listening port | `8080` |
