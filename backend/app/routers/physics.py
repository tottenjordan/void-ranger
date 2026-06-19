from fastapi import APIRouter

from app.models.schemas import (
    BestSpotRequest,
    CartesianResponse,
    DeepestVoidRequest,
    EfficiencyRequest,
    EfficiencyResponse,
    GalacticCoordsRequest,
)
from app.services.physics import (
    breakeven_task_seconds,
    compute_efficiency,
    earth_dilation_factor,
    find_best_spot,
    find_deepest_void,
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
    f_earth = earth_dilation_factor(req.scale)
    f_server = server_dilation_factor(req.x, req.y, req.z, req.scale)
    latency = light_latency(req.x, req.y, req.z, req.scale)
    result = compute_efficiency(req.task_seconds, f_earth, f_server, latency)
    return {
        **result,
        "latency_seconds": latency,
        "earth_dilation_factor": f_earth,
        "server_dilation_factor": f_server,
        "clock_advantage": f_server / f_earth,
        "breakeven_task_seconds": breakeven_task_seconds(f_earth, f_server, latency),
    }


@router.post("/api/physics/best-void", response_model=CartesianResponse)
async def best_void(req: DeepestVoidRequest):
    return find_deepest_void(req.max_distance_pc, req.scale)


@router.post("/api/physics/best-spot", response_model=CartesianResponse)
async def best_spot(req: BestSpotRequest):
    return find_best_spot(req.task_seconds, req.max_distance_pc, req.scale)
