# Backend Architecture & API Specification

The backend service is built using **FastAPI** (Python 3.10+) and runs in production on **Render.com** (or as a containerized web service). It connects to a **PostgreSQL** database hosted on **Neon.tech** and an S3-compatible object store on **Cloudflare R2**.

---

## 1. Directory Structure

```text
code/backend/
├── build_static.py            # Static site generator for CI/CD and offline bundles
├── Dockerfile.static          # Lightweight Nginx Alpine Dockerfile for GHCR image
├── nginx.conf                 # Nginx server configuration for the static bundle
├── pyproject.toml             # Project dependencies and packaging definition
├── src/
│   ├── app/
│   │   ├── main.py            # FastAPI application entrypoint, middleware, and routers
│   │   └── auth.py            # API key validation, cookie handling, and iframe referer logic
│   ├── analyze_uploads/
│   │   └── analyze_uploads.py # Scanner for media files in uploaded archives
│   ├── config/
│   │   └── config.py          # Environment configuration loader
│   ├── database/
│   │   └── database.py        # SQLAlchemy models (Game, ZipUpload, Asset) and session
│   ├── file_uploads/
│   │   └── file_uploads.py    # ZIP unpacking, validation, and storage coordination
│   ├── game/
│   │   ├── game.py            # CRUD operations, dynamic asset routing, and testing routes
│   │   └── internet_assets.py # In-flight internet asset downloader and URL rewriter
│   ├── home-screen/           # Templates, retro pixel fonts, CSS, and JS for static builds
│   ├── storage/
│   │   └── uploads_storage.py # S3fs-based abstraction over Cloudflare R2 / S3
│   └── trigger_build/
│       └── trigger_build.py   # GitHub App client, workflow dispatch, and status polling
└── tests/
    └── test_placeholder.py    # Pytest test suites
```

---

## 2. Configuration & Environment Variables

The backend loads configuration from `src/.env` or `.env` using `python-dotenv`:

| Environment Variable | Description | Default / Example |
| :--- | :--- | :--- |
| `UPLOADS_BACKEND` | Storage backend type (must be set to `s3`) | `s3` |
| `UPLOADS_REMOTE_ROOT` | S3 URI root for storing game files | `s3://arcade-bucket/uploads` |
| `S3_ENDPOINT_URL` | S3-compatible API endpoint | `https://<account-id>.r2.cloudflarestorage.com` |
| `S3_ACCESS_KEY_ID` | S3 Access Key ID | Cloudflare R2 Access Key |
| `S3_SECRET_ACCESS_KEY` | S3 Secret Access Key | Cloudflare R2 Secret Key |
| `S3_SESSION_TOKEN` | Optional S3 session token | (Optional) |
| `DB_STRING` | SQLAlchemy database connection URI | `postgresql://user:pass@ep-....neon.tech/arcade` |
| `LOG_LEVEL` | Application logging level | `INFO` or `DEBUG` |
| `DB_LOG_LEVEL` | SQLAlchemy query logging level | `ERROR` |
| `API_KEY` | Secret token required for admin endpoints | Shared API Key |
| `CORS_ALLOWED_ORIGINS` | JSON list of allowed origins | `["https://arcade.example.com", "http://localhost:9000"]` |
| `GITHUB_APP_ID` | GitHub App ID for build dispatch | `123456` |
| `GITHUB_PRIVATE_KEY_PATH` | Path to GitHub App `.pem` private key | `private/ua-arcade-deploy.private-key.pem` |
| `GITHUB_INSTALLATION_ID` | GitHub App installation ID on target repo | `98765432` |
| `GITHUB_REPO_OWNER` | GitHub organization / user owning the repo | `thomas-more-digital-innovation` |
| `GITHUB_REPO_NAME` | GitHub repository name | `2526-UAnt-007-Arcade-cabinet` |

---

## 3. Database Models & Schema

The relational schema is defined in [`src/database/database.py`](../code/backend/src/database/database.py) using SQLAlchemy 2.0 Declarative Models:

```mermaid
erDiagram
    GAME ||--o{ ZIP_UPLOAD : "has"
    GAME ||--o{ ASSET : "has overrides"

    GAME {
        UUID id PK
        string name "Game title (max 120 chars)"
        string description "Game story/instructions (max 2000 chars)"
        boolean is_active "Whether included on the arcade cabinet"
    }

    ZIP_UPLOAD {
        UUID id PK
        string name "Unique archive filename (<uuid>.zip)"
        UUID game_id FK "References GAME.id"
        string game_root_uri "S3 URI pointing to directory with index.html"
    }

    ASSET {
        UUID id PK
        UUID game_id FK "References GAME.id"
        string original_path "Relative path inside game archive"
        string path "S3 URI of replacement file"
    }
```

### Model Descriptions
1. **`Game`**:
   - Represents a playable game title.
   - `is_active`: Controls whether the game is included when generating static builds for the arcade machine.
   - `description`: Contains instructions and lore shown on the cabinet selection overlay before launching.
2. **`ZipUpload`**:
   - Tracks the uploaded ZIP archive and its extracted location.
   - `game_root_uri`: Caches the exact S3 URI containing `index.html`. This optimization eliminates recursive S3 listings on every file lookup.
3. **`Asset`**:
   - Stores manual asset replacements (such as custom school logos, modified character sprites, or audio clips).
   - Maps `original_path` (e.g., `assets/sprites/player.png`) to the replacement's S3 URI.

---

## 4. Object Storage Layout (Cloudflare R2)

All game files and asset overrides are stored in Cloudflare R2 using the following hierarchy:

```text
s3://<bucket>/<UPLOADS_REMOTE_ROOT>/
├── uploaded_zips/
│   └── <uuid>.zip                          # Pristine uploaded ZIP archive
├── extracted_games/
│   └── <uuid>.zip/                         # Extracted game directory tree
│       ├── index.html                      # Primary entrypoint
│       ├── js/                             # JavaScript game logic
│       ├── assets/                         # Sprites, audio, stylesheets
│       └── _downloaded_assets/             # Offline-localized external dependencies
└── asset_overrides/
    └── <game_id>/
        └── <sanitized_relative_path>.<ext> # Uploaded replacement asset
```

---

## 5. Internet Asset Localization Engine

Web games created with frameworks like Phaser, Babylon, or vanilla HTML5 often rely on external CDN links (e.g. `https://cdn.jsdelivr.net/...`, `https://fonts.googleapis.com/...`, sound effects hosted on external servers).

The module [`src/game/internet_assets.py`](../code/backend/src/game/internet_assets.py) solves the offline dilemma:

1. **Extraction**: When a game is uploaded, files are extracted to a local temporary folder.
2. **Scan**: All text files (`.html`, `.htm`, `.css`, `.js`, `.mjs`, `.json`, `.xml`, `.svg`) are scanned with regex for `http(s)://` URLs.
3. **Download**: Remote resources (up to 25MB each) are downloaded into `_downloaded_assets/`. Files are named with a SHA-256 hash of their URL plus the detected file extension.
4. **URL Rewriting**: The original remote URL strings in the code are replaced with relative paths (or `/games/<game_id>/_downloaded_assets/...`).
5. **Offline Ready**: When bundled onto the Raspberry Pi, the game runs completely independent of internet access.

---

## 6. Dynamic Asset Serving & Overrides

When testing games via the web UI or previewing assets, [`src/game/game.py`](../code/backend/src/game/game.py) dynamically intercepts requests:

1. **Route**: `GET /games/{game_id}/{file_path:path}`
2. **Lookup**:
   - The backend checks the `Asset` table for a record matching `game_id` and `original_path = normalized(file_path)`.
   - **If override exists**: Streams the custom file from `asset_overrides/`.
   - **If no override exists**: Streams the file from `extracted_games/<zip>/...`.
3. **Dedicated Endpoints**:
   - `GET /games/{game_id}/original/{file_path}`: Always serves the un-overridden asset.
   - `GET /games/{game_id}/replacement/{file_path}`: Serves the replacement asset directly.
   - `GET /games/{game_id}/test`: Serves the root HTML document in test mode for iframe preview.

---

## 7. GitHub Actions Dispatcher (`trigger_build`)

When the user clicks "Update Pi" in the frontend:
1. **Endpoint**: `POST /trigger-build/trigger-workflow`
2. **Database Dump**: Queries all active games (`Game.is_active == True`), along with their `ZipUpload` and `Asset` override records.
3. **GitHub App Authentication**:
   - The backend contains a reference to a private key (`.pem`), generated from a GitHub App that acts to trigger the Docker build workflows.
   - **GitHub App Permissions**:
     - `Actions`: `Read-only` (workflows, workflow runs, and artifacts to poll build progress).
     - `Contents`: `Read and write` (Repository contents, commits, branches, downloads, releases, and merges to emit repository dispatch events).
   - **Required Settings**:
     - `GITHUB_PRIVATE_KEY_PATH`: Path to the `.pem` private key file (e.g. `private/ua-arcade-deploy.2026-04-22.private-key.pem`).
     - `GITHUB_APP_ID`: App ID found at the top of the GitHub App settings page.
     - `GITHUB_INSTALLATION_ID`: Installation ID found in the URL once the app is installed in the organization (example: `https://github.com/organizations/Thomas-More-Digital-Innovation/settings/installations/<installation-id>`).
4. **Dispatch**: Sends a `repository_dispatch` event with `event_type: 'trigger'` and `client_payload: db_dump`.
5. **Monitoring**: `GET /trigger-build/workflow-status` polls the latest GitHub workflow run, retrieving job steps (`total_steps`, `completed_steps`, `current_step`) to drive the frontend progress bar.

---

## 8. API Endpoints Reference

### Health Check
- `GET /`: Health check endpoint. Returns `{"message": "Hello World"}`.

### Games Management (`/games`)
- `GET /games/`: List all games (protected).
- `POST /games/`: Create a new game entry (`{ name, description, is_active }`) (protected).
- `PUT /games/{game_id}`: Update game metadata or active status (protected).
- `DELETE /games/{game_id}`: Delete a game, its database records, raw ZIPs, extracted trees, and overrides from S3 (protected).
- `GET /games/{game_id}/test`: Launch game in test mode inside an iframe.
- `GET /games/{game_id}/{file_path:path}`: Serve game files with automatic override resolution.
- `GET /games/{game_id}/original/{file_path:path}`: Serve original game file.
- `GET /games/{game_id}/replacement/{file_path:path}`: Serve replacement game file.
- `GET /games/{game_id}/analyzed-assets`: Discover all media assets (images, audio) inside a game (protected).
- `GET /games/{game_id}/asset-overrides`: Retrieve list of all registered overrides for a game (protected).
- `POST /games/{game_id}/upload-asset`: Upload a replacement media asset for a game (protected).
- `DELETE /games/{game_id}/asset-override`: Delete a specific asset override (protected).

### File Uploads (`/file-uploads`)
- `POST /file-uploads/upload-zip`: Upload a game ZIP archive, extract, localize internet assets, upload to S3, and associate with a game (protected).

### Build Dispatch (`/trigger-build`)
- `POST /trigger-build/trigger-workflow`: Trigger the GitHub Actions CI/CD static build (protected).
- `GET /trigger-build/workflow-status`: Retrieve current build status and step progress (protected).

