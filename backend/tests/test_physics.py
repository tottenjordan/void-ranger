import math

import pytest

from app.services.physics import (
    breakeven_task_seconds,
    compute_efficiency,
    earth_dilation_factor,
    galactic_to_cartesian,
    gravitational_dilation,
    light_latency,
    local_potential,
    server_dilation_factor,
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
    assert light_latency(1, 0, 0) > 0


# --- Gravitational potential & dilation -------------------------------------

def test_local_potential_finite_everywhere():
    # Even far outside the catalog the potential is finite and non-negative.
    assert local_potential(100000, 100000, 100000) >= 0


def test_local_potential_higher_near_origin_than_deep_void():
    # The origin sits in the dense solar neighborhood; a far point is a void.
    assert local_potential(0, 0, 0) > local_potential(5000, 5000, 5000)


def test_gravitational_dilation_void_is_near_one():
    # Negligible potential -> clock ~ flat spacetime.
    assert abs(gravitational_dilation(0.0) - 1.0) < 1e-9


def test_gravitational_dilation_decreases_with_potential():
    shallow = gravitational_dilation(1e5)
    deep = gravitational_dilation(1e7)
    assert deep < shallow < 1.0


def test_server_faster_in_void_than_at_earth():
    f_earth = earth_dilation_factor()
    f_void = server_dilation_factor(5000, 5000, 5000)
    assert f_void > f_earth  # void server's clock runs faster than Earth's


def test_compute_efficiency_void_advantage():
    # Equal clocks -> compute time equals task time.
    eq = compute_efficiency(100, 0.9, 0.9, 0)
    assert abs(eq["earth_compute_time"] - 100) < 1e-9

    # Faster server (higher f_server) -> less Earth time elapses.
    faster = compute_efficiency(100, 0.9, 1.0, 0)
    assert faster["earth_compute_time"] < 100
    assert faster["net_gain"] > 0


def test_compute_efficiency_latency_can_cause_loss():
    result = compute_efficiency(100, 0.9, 1.0, 50)
    assert result["earth_wait_time"] == result["earth_compute_time"] + 50
    assert result["net_gain"] < 0


def test_breakeven_positive_when_server_faster():
    # server faster than Earth (f_server > f_earth) → finite positive breakeven
    be = breakeven_task_seconds(f_earth=0.9, f_server=1.0, latency_seconds=100.0)
    # 100 / (1 - 0.9/1.0) = 100 / 0.1 = 1000
    assert be == pytest.approx(1000.0)


def test_breakeven_none_when_server_not_faster():
    # server same/slower than Earth → never breaks even
    assert breakeven_task_seconds(0.9, 0.9, 100.0) is None
    assert breakeven_task_seconds(0.9, 0.8, 100.0) is None
