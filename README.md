# us-travel-planner — Conversational US Road-Trip & Motorcycle Planner

Production-grade **Google ADK + Gemini 2.5** conversational agent that plans multi-day US road trips
and motorcycle routes: live rental lookup via Firestore, trip budget sandboxing, RAG-backed travel
guidelines, real-time AI-generated destination photography, and full A2A protocol support. Deployed
on Vertex AI Agent Runtime with a Cloud Run frontend.

> Ported from a live build session with Google developer advocates — original at
> [buildwithgemini-us-travel-planner](https://github.com/bganguly/buildwithgemini-us-travel-planner).
> This repo migrates all Qwiklabs-hardcoded values to environment variables and targets the
> `bikram-java` GCP project.

## Live Service

| Endpoint | URL |
|---|---|
| **Frontend (Cloud Run)** | _(set after `agents-cli deploy` + Cloud Run deploy)_ |
| **Local dev server** | `http://localhost:8085` (FastAPI proxy + chat UI) |
| **Media bucket** | `gs://us-travel-planner-media-bikram` (public read) |

---

## Setup — First-time GCP bootstrap

Run these once to provision the GCS bucket, seed Firestore, and create the RAG corpus before the first `agents-cli deploy`.

Enable required APIs:

```bash
gcloud config set project bikram-java
gcloud services enable aiplatform.googleapis.com firestore.googleapis.com storage.googleapis.com run.googleapis.com
```

Create the public GCS bucket and copy the RAG source and stock images:

```bash
gcloud storage buckets create gs://us-travel-planner-media-bikram --location=us-east1 --uniform-bucket-level-access
gcloud storage buckets add-iam-policy-binding gs://us-travel-planner-media-bikram --member=allUsers --role=roles/storage.objectViewer
gsutil -m cp -r gs://us-travel-planner-media-qwiklabs-04/rag gs://us-travel-planner-media-bikram/
gsutil -m cp -r gs://us-travel-planner-media-qwiklabs-04/stock gs://us-travel-planner-media-bikram/
```

Copy `.env.example` to `.env` and fill in `RAG_CORPUS_NAME` after the next step:

```bash
cp .env.example .env
```

Seed Firestore motorcycle rentals:

```bash
uv run python scripts/seed_firestore.py
```

Create the Vertex AI RAG corpus (takes ~2–3 min):

```bash
uv run python scripts/create_rag_corpus.py
```

The corpus resource name is printed as `CREATED_CORPUS_NAME` and saved to `rag_corpus_name.txt`. Copy it into `.env`:

```
RAG_CORPUS_NAME=projects/527485542788/locations/us-central1/ragCorpora/<id>
```

---

## Using the App

1. **Plan a trip** — describe your dates, departure city, riding experience, and budget. The agent retains preferences across sessions via Vertex AI Memory Bank.
2. **Route lookup** — ask for a specific highway (Scenic Byway 12, Zion Mount Carmel, Route 66, Grand Canyon South Rim) to get mileage, difficulty, waypoints, and season.
3. **Rental search** — query available motorcycles by city and type (Cruiser, Adventure Touring) from the Firestore `motorcycle_rentals` collection.
4. **Budget estimation** — the sandbox code executor computes itemized trip costs: rental, fuel (45 MPG × $3.85/gal), lodging tier, meals, and park passes.
5. **Destination imagery** — the agent calls `generate_destination_image` / `generate_domain_item_image` (gemini-3.1-flash-lite-image) and returns a public GCS-hosted photo URL inline.
6. **Travel guidelines** — `consult_travel_instructions` queries the Vertex AI RAG corpus seeded from `rag/instructions.txt` for speed limits, operating hours, and park rules.

### Sample prompt

> "Plan a 7-day motorcycle road trip from Salt Lake City or Las Vegas covering Utah's Scenic Byway 12 and the Grand Canyon, including local motorcycle rental options and daily riding distance breakdowns under $2,500."

---

| Area | Stack / Detail |
|---|---|
| **Agent framework** | Google ADK — `Agent`, `App`, `Runner`; `PreloadMemoryTool` injects cross-session facts on every turn |
| **Model** | gemini-3.6-flash (conversation + tool routing); gemini-3.1-flash-lite-image (image generation) |
| **Session & memory** | Vertex AI Session Service + Vertex AI Memory Bank (cross-session user preference recall) |
| **Code execution** | `AgentEngineSandboxCodeExecutor` — Python sandbox on the Reasoning Engine for budget math (no-op locally until deployed) |
| **RAG** | Vertex AI Serverless RAG corpus (`text-embedding-005`); `LlmParserConfig` with gemini-2.5-flash + custom extraction prompt; 512-token chunks, 100-token overlap |
| **Firestore** | `motorcycle_rentals` collection — city/type-filtered reads + upserts via ADK tools |
| **GCS** | Public bucket `us-travel-planner-media-bikram`; subfolders: `generated_items/`, `postcards/`, `stock/`, `rag/` |
| **A2A protocol** | Full A2A JSON-RPC + agent-card endpoints via `a2a-sdk`; streaming + ADK executor extension |
| **Telemetry** | Cloud Trace, BigQuery, Cloud Logging (opt-in via `GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY`) |
| **Frontend** | Mesop-based UI in `frontend/`; proxies chat to the FastAPI backend |
| **IaC** | Terraform in `deployment/terraform/single-project/` |

---

## Architecture

```
User browser
  └─ Cloud Run (Mesop frontend, us-east1)
       └─ HTTP proxy → FastAPI backend (local or Agent Runtime)
            ├─ /api/**           ADK web routes (adk_api)
            ├─ /a2a/app/**       A2A JSON-RPC + agent-card
            └─ /reasoning/**     Vertex AI Console Playground adapter

FastAPI (app/fast_api_app.py)
  └─ Runner (shared session / memory / artifact services)
       └─ root_agent  [gemini-3.6-flash]
            ├─ PreloadMemoryTool ──────────────────► Vertex AI Memory Bank
            ├─ get_weather / get_current_time        (in-process stubs)
            ├─ consult_travel_instructions ──────────► Vertex AI RAG Corpus (us-central1)
            │                                           gs://us-travel-planner-media-bikram/rag/instructions.txt
            ├─ list/get/add_motorcycle_rental ───────► Firestore (motorcycle_rentals)
            ├─ calculate_trip_budget ────────────────► AgentEngineSandbox (Python executor)
            ├─ get_scenic_route_highlights            (in-process route database)
            ├─ generate_destination_image ───────────► gemini-3.1-flash-lite-image
            │   └─ upload ──────────────────────────► GCS (postcards/)
            └─ generate_domain_item_image ───────────► gemini-3.1-flash-lite-image
                └─ save artifact + upload ──────────► GCS (generated_items/)

Vertex AI Agent Runtime (us-east1)  ← set after agents-cli deploy
  └─ reasoningEngine/<id>
       ├─ Session Service   (cross-request session persistence)
       └─ Memory Bank       (cross-session user preference recall)
```

---

## Running

Install dependencies and launch the local playground:

```bash
uvx google-agents-cli setup
```

```bash
agents-cli install
```

```bash
agents-cli playground
```

Open `http://localhost:8085` to chat with the agent.

### Key commands

| Command | What it does |
|---|---|
| `agents-cli playground` | Local dev server with hot-reload |
| `agents-cli eval` | Run eval suite (`tests/eval/`) |
| `uv run pytest tests/unit tests/integration` | Unit + integration tests |
| `agents-cli deploy` | Deploy/update agent on Vertex AI Agent Runtime |
| `agents-cli publish gemini-enterprise` | Register with Gemini Enterprise via A2A |
| `agents-cli scaffold enhance` | Add CI/CD pipelines + Terraform infra |
| `uv run python scripts/create_rag_corpus.py` | (Re)create and seed the RAG corpus |
| `uv run python scripts/seed_firestore.py` | Seed the Firestore `motorcycle_rentals` collection |

---

## Cost

| Resource | Cost |
|---|---|
| **Vertex AI Agent Runtime** | Per-invocation (Reasoning Engine); ~$0 when idle |
| **Cloud Run frontend** | Scale-to-zero; negligible at demo traffic levels |
| **Firestore** | Free tier covers demo-scale read/write |
| **Vertex AI RAG** | Serverless mode — pay per query, no always-on node |
| **GCS media bucket** | ~$0.02/GB/month; demo volume is negligible |
| **Gemini models** | Per-token (chat) + per-image (generation) |

---

## Key Design Decisions

| Concern | Approach |
|---|---|
| **Cross-session memory** | `PreloadMemoryTool` injects recalled user facts (budget, riding level, departure city) into every turn — no explicit "remember this" prompt needed |
| **Image delivery** | AI-generated images are uploaded to a public GCS bucket and returned as HTTPS URLs — no base64 in the chat response, frontend renders them inline |
| **RAG parsing** | `LlmParserConfig` with gemini-2.5-flash extracts structured travel rules from free-text docs, improving retrieval precision over naive chunking |
| **Sandbox budget math** | `AgentEngineSandboxCodeExecutor` runs Python arithmetic in an isolated environment — avoids hallucinated totals from pure LLM arithmetic; disabled locally until `agents-cli deploy` populates `deployment_metadata.json` |
| **Shared services** | `services.py` registers session, memory, and artifact services under `shared://` URIs so the ADK API, A2A path, and Reasoning Engine adapter share one consistent state |
| **A2A interoperability** | All agent capabilities are exposed on the A2A JSON-RPC path (`/a2a/app`), allowing other agents or Gemini Enterprise to call this agent as a sub-agent |
| **Environment portability** | All GCP project IDs, bucket names, and resource IDs are read from env vars (with `bikram-java` defaults); no Qwiklabs credentials hardcoded |
