# To install (dev):
python3 -m venv .venv
source ./.venv/bin/activate
pip install .
uvicorn src.app.main:app --reload