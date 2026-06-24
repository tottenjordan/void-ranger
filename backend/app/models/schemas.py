from typing import Literal

from pydantic import BaseModel


class GalacticCoordsRequest(BaseModel):
    distance: float
    longitude: float
    latitude: float


class CartesianResponse(BaseModel):
    x: float
    y: float
    z: float


class EfficiencyRequest(BaseModel):
    x: float
    y: float
    z: float
    task_seconds: float
    scale: Literal["solar", "cosmic", "deepfield"] = "solar"


class DeepestVoidRequest(BaseModel):
    # max_distance_pc is the search radius in the scale's length unit:
    # parsecs for "solar", megaparsecs for "cosmic" and "deepfield".
    max_distance_pc: float = 300.0
    scale: Literal["solar", "cosmic", "deepfield"] = "solar"


class BestSpotRequest(BaseModel):
    task_seconds: float
    # max_distance_pc is the search radius in the scale's length unit:
    # parsecs for "solar", megaparsecs for "cosmic" and "deepfield".
    max_distance_pc: float = 300.0
    scale: Literal["solar", "cosmic", "deepfield"] = "solar"


class EfficiencyResponse(BaseModel):
    earth_compute_time: float
    earth_wait_time: float
    net_gain: float
    latency_seconds: float
    earth_dilation_factor: float
    server_dilation_factor: float
    clock_advantage: float
    breakeven_task_seconds: float | None = None
