from fastapi import APIRouter

from app.models.schemas import (
    CartesianResponse,
    EfficiencyRequest,
    EfficiencyResponse,
    GalacticCoordsRequest,
)
from app.services.physics import (
    compute_efficiency,
    earth_dilation_factor,
    galactic_to_cartesian,
    light_latency,
    server_dilation_factor,
)

router = APIRouter()


@router.post("/api/physics/cartesian", response_model=CartesianResponse)
async def to_cartesian(req: GalacticCoordsRequest):
    return galactic_to_cartesian(req.distance, req.longitude, req.latitude)


@router.post("/api/physics/efficiency", response_model=EfficiencyResponse)
async def efficiency(req: EfficiencyRequest):
    f_earth = earth_dilation_factor()
    f_server = server_dilation_factor(req.x, req.y, req.z)
    latency = light_latency(req.x, req.y, req.z)
    result = compute_efficiency(req.task_seconds, f_earth, f_server, latency)
    return {
        **result,
        "latency_seconds": latency,
        "earth_dilation_factor": f_earth,
        "server_dilation_factor": f_server,
        "clock_advantage": f_server / f_earth,
    }
