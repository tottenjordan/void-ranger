import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "stars.json"


@router.get("/api/stars")
async def get_stars():
    if not DATA_PATH.exists():
        raise HTTPException(status_code=404, detail="stars.json not found — run process_stars.py first")
    with open(DATA_PATH) as f:
        return json.load(f)
