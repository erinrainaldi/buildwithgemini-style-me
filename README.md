# style-me

Simple ReAct agent
Agent generated with `agents-cli` version `1.4.0`

## Project Structure

```
style-me/
├── app/                       # Core AI Stylist agent (ADK + A2UI)
│   ├── agent.py               # Stylist logic, mannequin image generation, tools
│   ├── fast_api_app.py        # FastAPI Backend server
│   └── app_utils/             # App utilities and helpers
├── frontend/                  # Web app (FastAPI proxy + luxury UI + closet manager)
│   ├── main.py                # Image extraction, GCS caching, and A2A chat proxy
│   ├── static/index.html      # Responsive luxury wardrobe manager & chat interface
│   └── Dockerfile             # Container definition for Cloud Run
├── sync_gcs_closet.py         # Batch image ingestion & Gemini Vision auto-cataloger
├── tests/                     # Unit, integration, and load tests
├── GEMINI.md                  # AI-assisted development guide
└── pyproject.toml             # Project dependencies
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

> 💡 **Tip:** Use [Antigravity CLI](https://antigravity.google/) for AI-assisted development - project context is pre-configured in `GEMINI.md`.

## Requirements

Before you begin, ensure you have:
- **uv**: Python package manager (used for all dependency management in this project) - [Install](https://docs.astral.sh/uv/getting-started/installation/) ([add packages](https://docs.astral.sh/uv/concepts/dependencies/) with `uv add <package>`)
- **agents-cli**: Agents CLI - Install with `uv tool install google-agents-cli`
- **Google Cloud SDK**: For GCP services - [Install](https://cloud.google.com/sdk/docs/install)


## Quick Start

Install `agents-cli` and its skills if not already installed:

```bash
uvx google-agents-cli setup
```

Install required packages:

```bash
agents-cli install
```

Test the agent with a local web server:

```bash
agents-cli playground
```

You can also use features from the [ADK](https://adk.dev/) CLI with `uv run adk`.

## Commands

| Command              | Description                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------- |
| `agents-cli install` | Install dependencies using uv                                                         |
| `agents-cli playground` | Launch local development environment                                                  |
| `agents-cli lint`    | Run code quality checks                                                               |
| `agents-cli eval`    | Evaluate agent behavior (generate, grade, analyze, and more — see `agents-cli eval --help`) |
| `uv run pytest tests/unit tests/integration` | Run unit and integration tests                                                        |
| `agents-cli deploy`  | Deploy agent to Agent Runtime                                                                |
| `agents-cli publish gemini-enterprise` | Register deployed agent to Gemini Enterprise                    || [A2A Inspector](https://github.com/a2aproject/a2a-inspector) | Launch A2A Protocol Inspector                                                        |

## 🛠️ Project Management

| Command | What It Does |
|---------|--------------|
| `agents-cli scaffold enhance` | Add CI/CD pipelines and Terraform infrastructure |
| `agents-cli infra cicd` | One-command setup of entire CI/CD pipeline + infrastructure |
| `agents-cli scaffold upgrade` | Auto-upgrade to latest version while preserving customizations |

---

## Development

Edit your agent logic in `app/agent.py` and test with `agents-cli playground` - it auto-reloads on save.

## Deployment

```bash
gcloud config set project <your-project-id>
agents-cli deploy
```

To add CI/CD and Terraform, run `agents-cli scaffold enhance`.
To set up your production infrastructure, run `agents-cli infra cicd`.

## Observability

Built-in telemetry exports to Cloud Trace, BigQuery, and Cloud Logging.

## A2A Inspector

This agent supports the [A2A Protocol](https://a2a-protocol.org/). Use the [A2A Inspector](https://github.com/a2aproject/a2a-inspector) to test interoperability.
See the [A2A Inspector docs](https://github.com/a2aproject/a2a-inspector) for details.
