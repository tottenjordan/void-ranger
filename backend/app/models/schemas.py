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


class EfficiencyResponse(BaseModel):
    earth_compute_time: float
    earth_wait_time: float
    net_gain: float
    latency_seconds: float
    earth_dilation_factor: float
    server_dilation_factor: float
    clock_advantage: float
