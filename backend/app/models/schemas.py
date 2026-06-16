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
    mass_kg: float       # mass of gravitational well Earth sits in
    radius_m: float      # Earth's distance from center of that mass


class EfficiencyResponse(BaseModel):
    earth_compute_time: float
    earth_wait_time: float
    net_gain: float
    latency_seconds: float
    dilation_factor: float
