import math

from app.services.physics import (
    SOLAR_MASS,
    compute_efficiency,
    galactic_to_cartesian,
    light_latency,
    lorentz_factor,
    time_dilation_factor,
)


def test_galactic_to_cartesian_along_x():
    result = galactic_to_cartesian(1, 0, 0)
    assert abs(result["x"] - 1.0) < 1e-10
    assert abs(result["y"]) < 1e-10
    assert abs(result["z"]) < 1e-10


def test_galactic_to_cartesian_along_y():
    result = galactic_to_cartesian(1, 90, 0)
    assert abs(result["x"]) < 1e-10
    assert abs(result["y"] - 1.0) < 1e-10
    assert abs(result["z"]) < 1e-10


def test_galactic_to_cartesian_along_z():
    result = galactic_to_cartesian(1, 0, 90)
    assert abs(result["x"]) < 1e-10
    assert abs(result["y"]) < 1e-10
    assert abs(result["z"] - 1.0) < 1e-10


def test_light_latency_origin():
    assert light_latency(0, 0, 0) == 0.0


def test_light_latency_positive():
    latency = light_latency(1, 0, 0)
    assert latency > 0


def test_time_dilation_far_from_mass():
    factor = time_dilation_factor(SOLAR_MASS, 1e15)
    assert abs(factor - 1.0) < 1e-6


def test_time_dilation_closer_to_mass():
    far = time_dilation_factor(SOLAR_MASS, 1e15)
    close = time_dilation_factor(SOLAR_MASS, 1e10)
    assert close < far


def test_lorentz_factor_at_rest():
    assert lorentz_factor(0) == 1.0


def test_lorentz_factor_increases_with_speed():
    slow = lorentz_factor(1000)
    fast = lorentz_factor(100000)
    assert fast > slow


def test_compute_efficiency_zero_latency():
    result = compute_efficiency(100, 0.5, 0)
    assert result["earth_compute_time"] == 50.0
    assert result["earth_wait_time"] == 50.0
    assert result["net_gain"] == 50.0


def test_compute_efficiency_with_latency():
    result = compute_efficiency(100, 0.5, 200)
    assert result["earth_compute_time"] == 50.0
    assert result["earth_wait_time"] == 250.0
    assert result["net_gain"] == -150.0
