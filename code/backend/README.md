# To install (dev):
python3 -m venv .venv
source ./.venv/bin/activate
pip install -e .
uvicorn src.app.main:app --reload