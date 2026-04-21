# Development
## To install (dev):
```bash
python3 -m venv .venv
source ./.venv/bin/activate
pip install -e .
```

## Running the Backend:
```bash
uvicorn src.app.main:app --reload
```

# Static Build (for Arcade Cabinet)
This project includes a script to generate a static, offline-ready version of the arcade.

## 1. Generate the static site:
Ensure your `src/.env` has S3 credentials and run:
```bash
python3 build_static.py
```
This generates a `dist/` folder.

## 2. Serve the static site locally:
To preview the static build, you must use a local web server (to handle absolute paths correctly):
```bash
cd dist
python3 -m http.server 8080
```
Then visit: http://localhost:8080