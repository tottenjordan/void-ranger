from fastapi import APIRouter

from app.models.schemas import (
    CartesianResponse,
    EfficiencyRequest,
    EfficiencyResponse,
    GalacticCoordsRequest,
)
from app.services.physics import (
    compute_efficiency,
    galactic_to_cartesian,
    light_latency,
    time_dilation_factor,
)

router = APIRouter()


@router.post("/api/physics/cartesian", response_model=CartesianResponse)
async def to_cartesian(req: GalacticCoordsRequest):
    coords = galactic_to_cartesian(req.distance, req.longitude, req.latitude)
    return coords


@router.post("/api/physics/efficiency", response_model=EfficiencyResponse)
async def efficiency(req: EfficiencyRequest):
    dilation = time_dilation_factor(req.mass_kg, req.radius_m)
    latency = light_latency(req.x, req.y, req.z)
    result = compute_efficiency(req.task_seconds, dilation, latency)
    return {
        **result,
        "latency_seconds": latency,
        "dilation_factor": dilation,
    }
