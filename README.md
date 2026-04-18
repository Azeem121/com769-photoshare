# PhotoShare — Cloud-Native Photo Sharing (COM769)

[![CI/CD — Build, Test & Deploy](https://github.com/<YOUR_GITHUB_USERNAME>/ScalableDemoApp/actions/workflows/deploy.yml/badge.svg)](https://github.com/<YOUR_GITHUB_USERNAME>/ScalableDemoApp/actions/workflows/deploy.yml)

> **COM769 — Scalable Advanced Software Solutions**  
> A cloud-native photo-sharing web application (Instagram-style) deployed entirely on Azure free-tier services.

---

## Architecture

```
Browser
  │
  ├─► Azure CDN (Standard_Microsoft — 15 GB/month free)
  │     └─► Azure Static Web Apps (Free — frontend + SWA auth)
  │               │  /.auth/login/github or /aad
  │               │  /.auth/me  → user identity + roles
  │               └─► /api/*  ─── proxy ───►  Azure Functions
  │
  └─► Azure Functions (Consumption plan — 1M invocations free)
        ├── POST   /api/GetRoles          → custom role assignment
        ├── GET    /api/health            → health check
        ├── POST   /api/photos/upload     → upload photo (creator)
        ├── GET    /api/photos/my         → creator's own photos
        ├── DELETE /api/photos/{id}       → delete photo (creator)
        ├── GET    /api/photos            → list / search (public)
        ├── GET    /api/photos/{id}       → photo + comments + rating
        ├── POST   /api/photos/{id}/comment → add comment (consumer)
        └── POST   /api/photos/{id}/rate    → rate 1–5 stars (consumer)
              │
              ├─► Azure Cosmos DB (Free tier — 1000 RU/s, 25 GB)
              │     containers: users · photos · comments · ratings
              │
              ├─► Azure Blob Storage (Free for 12 months — 5 GB)
              │     container: photos  (public blob access)
              │
              └─► Azure Computer Vision (Free tier — 5 000 calls/month)
                    auto-tags, description, OCR on every upload
```

---

## User Roles

| Feature                         | Creator | Consumer |
|---------------------------------|:-------:|:--------:|
| Upload photos                   | ✅      | ❌       |
| Set title / caption / location  | ✅      | ❌       |
| Tag people in photos            | ✅      | ❌       |
| Delete own photos               | ✅      | ❌       |
| Browse photo feed               | ✅      | ✅       |
| Search (title, location, people)| ✅      | ✅       |
| Filter by AI tag                | ✅      | ✅       |
| Sort by date / rating           | ✅      | ✅       |
| View photo detail               | ✅      | ✅       |
| Comment on photos               | ❌      | ✅       |
| Rate photos (1–5 stars)         | ❌      | ✅       |

> Creator accounts are seeded directly in Cosmos DB — there is no public creator registration endpoint.

---

## Project Structure

```
ScalableDemoApp/
├── frontend/                        # Azure Static Web Apps
│   ├── index.html                   # Landing / login (GitHub + Microsoft)
│   ├── consumer.html                # Consumer feed (browse, search, rate, comment)
│   ├── creator.html                 # Creator dashboard (upload, manage)
│   ├── staticwebapp.config.json     # SWA routing, auth, role protection
│   └── shared/
│       ├── auth.js                  # /.auth/me wrapper, role-based redirect
│       ├── api.js                   # All backend fetch() calls
│       └── styles.css               # Responsive design system
│
├── backend/                         # Azure Functions (Python 3.11)
│   ├── host.json
│   ├── requirements.txt
│   ├── local.settings.json.template
│   ├── shared/
│   │   ├── auth_helper.py           # Parse x-ms-client-principal
│   │   ├── cosmos_client.py         # Cosmos DB connection + helpers
│   │   ├── blob_client.py           # Blob Storage upload/delete + CDN URLs
│   │   └── cognitive_service.py     # Azure Computer Vision analysis
│   ├── get_roles/                   # SWA custom roles (auto user creation)
│   ├── health/                      # GET /api/health
│   ├── photos_upload/               # POST /api/photos/upload
│   ├── photos_my/                   # GET /api/photos/my
│   ├── photos_delete/               # DELETE /api/photos/{id}
│   ├── photos_list/                 # GET /api/photos
│   ├── photo_get/                   # GET /api/photos/{id}
│   ├── comments_add/                # POST /api/photos/{id}/comment
│   ├── ratings_submit/              # POST /api/photos/{id}/rate
│   └── tests/
│       ├── test_auth_helper.py      # Unit tests (no Azure required)
│       └── test_health.py
│
├── infrastructure/                  # Bicep IaC
│   ├── main.bicep
│   ├── modules/
│   │   ├── staticwebapp.bicep
│   │   ├── functionapp.bicep        # Consumption plan + all app settings
│   │   ├── cosmosdb.bicep           # Free tier + serverless + 4 containers
│   │   ├── storage.bicep            # photos container (public blob)
│   │   └── cdn.bicep                # Standard_Microsoft + 7-day cache rules
│   └── parameters/
│       └── dev.parameters.json
│
├── .github/
│   └── workflows/
│       └── deploy.yml               # CI: lint → test → deploy backend + frontend
│
└── docs/
    ├── architecture.md
    └── api-spec.md
```

---

## Advanced Features (distinction-level)

### 1 — CI/CD Pipeline (GitHub Actions)
- **Lint** with flake8 on every push/PR
- **Unit tests** run before any deployment (`pytest backend/tests/`)
- **Backend deploy** to Azure Functions only if tests pass
- **Frontend deploy** to SWA with automatic PR preview environments
- **Bicep deploy** triggered only when `infrastructure/` files change
- PR preview URL automatically posted as a PR comment

### 2 — Azure Cognitive Services (Computer Vision)
- Every photo upload is analysed by Azure Computer Vision (free: 5 000 calls/month)
- **Auto-tags** (confidence > 60%) stored in `aiTags[]`
- **AI caption/description** stored in `aiDescription`
- **OCR text detection** stored in `aiText[]`
- Consumer view shows AI tags on every photo card and in the detail modal
- Consumer can **filter feed by AI tag** via a dropdown populated dynamically

### 3 — Azure CDN + Caching
- `blob_client.py` returns CDN URLs (`CDN_ENDPOINT_URL` env var) instead of raw blob URLs
- All photo blobs uploaded with `Cache-Control: public, max-age=604800, immutable` (7 days)
- CDN delivery policy caches images, CSS, JS at edge for 7 days
- SWA itself is fronted by Azure's global CDN automatically

---

## Local Development

### Prerequisites
```bash
# Azure Functions Core Tools v4
npm install -g azure-functions-core-tools@4

# Python virtual environment
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Configure
```bash
cp backend/local.settings.json.template backend/local.settings.json
# Edit local.settings.json and fill in:
#   COSMOS_DB_CONNECTION_STRING
#   BLOB_STORAGE_CONNECTION_STRING
#   CV_ENDPOINT + CV_KEY  (optional — AI analysis skipped if blank)
```

### Run backend
```bash
cd backend
func start
# Functions available at http://localhost:7071/api/
```

### Run frontend
```bash
# Option A — Azure SWA CLI (recommended, proxies /api/* to local Functions)
npm install -g @azure/static-web-apps-cli
cd frontend
swa start . --api-devserver-url http://localhost:7071

# Option B — simple HTTP server (auth won't work without SWA)
cd frontend
python -m http.server 3000
```

### Run tests
```bash
cd backend
pytest tests/ -v
```

---

## Azure Deployment

### 1. Provision infrastructure
```bash
az login
az group create --name rg-scalableapp --location uksouth
az deployment group create \
  --resource-group rg-scalableapp \
  --template-file infrastructure/main.bicep \
  --parameters infrastructure/parameters/dev.parameters.json
```

### 2. Seed a creator account
After deploying, create a user document directly in Cosmos DB (`photoshare` → `users` container):
```json
{
  "id": "<github-or-aad-user-id>",
  "userId": "<same-id>",
  "email": "creator@example.com",
  "displayName": "Creator Name",
  "role": "creator",
  "identityProvider": "github",
  "createdAt": "2025-01-01T00:00:00Z"
}
```

### 3. Configure GitHub Secrets

| Secret | Where to find |
|--------|--------------|
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | SWA resource → Overview → Manage deployment token |
| `AZURE_FUNCTIONAPP_PUBLISH_PROFILE` | Function App → Overview → Get publish profile |
| `AZURE_CREDENTIALS` | `az ad sp create-for-rbac --sdk-auth` output |
| `AZURE_SUBSCRIPTION_ID` | Azure portal |
| `AZURE_RG` | `rg-scalableapp` |

Push to `main` — the CI/CD pipeline handles the rest.

---

## Free Tier Limits

| Service | Free Allowance | Usage |
|---------|---------------|-------|
| Azure Static Web Apps | 100 GB bandwidth/month | Frontend hosting |
| Azure Functions | 1M executions + 400K GB-s/month | All API calls |
| Azure Cosmos DB | 1000 RU/s + 25 GB | All user/photo data |
| Azure Blob Storage | 5 GB LRS (12 months) | Photo files |
| Azure CDN (Standard_Microsoft) | 15 GB/month (12 months) | Edge caching |
| Azure Computer Vision | 5 000 calls/month | AI image analysis |
