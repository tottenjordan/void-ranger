from fastapi import APIRouter, HTTPException

from app.services.catalog import DATA_PATH, GALAXIES_PATH, load_galaxies, load_stars

router = APIRouter()


@router.get("/api/stars")
async def get_stars():
    """Serve the processed stars.json for the 3D galaxy map."""
    if not DATA_PATH.exists():
        raise HTTPException(status_code=404, detail="stars.json not found — run process_stars.py first")
    return load_stars()


@router.get("/api/galaxies")
async def get_galaxies():
    """Serve the processed galaxies.json for the 3D cosmic-web map."""
    if not GALAXIES_PATH.exists():
        raise HTTPException(status_code=404, detail="galaxies.json not found — run process_galaxies.py first")
    return load_galaxies()
