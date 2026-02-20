"""
tests/test_power_calculations.py
=================================
Spacecraft EPS — Unit Tests for Power Calculations

Verifies that every numerical output from power_model.py matches the values
computed in the engineering reference document:
    docs/avionics_power_budget_analysis.md

Document values under test:
    §2  P_nominal  = 60.65 W
    §4  P_EOL      = 75.8125 W  (document rounds to 75.81 W)
    §5  P_excess   = 104.1875 W (document rounds to 104.19 W)
    §6  t_charge   ≈ 0.32 h     (document rounds to 0.32 h / ~19 min)

All tests use pytest.approx() with tolerances appropriate to the document's
own rounding precision so that floating-point arithmetic differences do not
cause spurious failures.
"""

import pytest

from eps.config import (
    POWER_BUSES,
    EPS_MAX_POWER,
    EOL_DEGRADATION_FACTOR,
    SOLAR_ARRAY_POWER,
    BATTERY_CAPACITY_WH,
    BATTERY_INITIAL_SOC,
    BATTERY_CHARGING_EFFICIENCY,
)
from eps.power_model import (
    compute_nominal_power,
    compute_eol_power,
    compute_power_margin,
    compute_excess_solar_power,
    compute_battery_remaining_energy,
    compute_charging_time,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def nominal_result():
    """Pre-computed nominal power result reused across tests."""
    return compute_nominal_power(POWER_BUSES)


@pytest.fixture
def p_nominal(nominal_result):
    return nominal_result["P_nominal_W"]


@pytest.fixture
def p_eol(p_nominal):
    return compute_eol_power(p_nominal, EOL_DEGRADATION_FACTOR)


@pytest.fixture
def p_excess(p_eol):
    return compute_excess_solar_power(SOLAR_ARRAY_POWER, p_eol)


@pytest.fixture
def e_remaining():
    return compute_battery_remaining_energy(BATTERY_CAPACITY_WH, BATTERY_INITIAL_SOC)


# ---------------------------------------------------------------------------
# §2 — Nominal Power  (document value: 60.65 W)
# ---------------------------------------------------------------------------

class TestNominalPower:
    """§2: P_nominal = Σ V_i · I_i"""

    def test_total_nominal_power_matches_document(self, p_nominal):
        """P_nominal must equal 60.65 W as stated in §2."""
        assert p_nominal == pytest.approx(60.65, rel=1e-4), (
            f"Expected P_nominal = 60.65 W, got {p_nominal:.6f} W"
        )

    def test_per_bus_power_28v(self, nominal_result):
        """28 V bus: 28 × 1.2 = 33.6 W (§2)."""
        assert nominal_result["per_bus_W"][0] == pytest.approx(33.6, rel=1e-9)

    def test_per_bus_power_12v(self, nominal_result):
        """12 V bus: 12 × 0.8 = 9.6 W (§2)."""
        assert nominal_result["per_bus_W"][1] == pytest.approx(9.6, rel=1e-9)

    def test_per_bus_power_5v(self, nominal_result):
        """5 V bus: 5 × 2.5 = 12.5 W (§2)."""
        assert nominal_result["per_bus_W"][2] == pytest.approx(12.5, rel=1e-9)

    def test_per_bus_power_3v3(self, nominal_result):
        """3.3 V bus: 3.3 × 1.5 = 4.95 W (§2)."""
        assert nominal_result["per_bus_W"][3] == pytest.approx(4.95, rel=1e-9)

    def test_per_bus_count(self, nominal_result):
        """Result must contain exactly one entry per bus defined in config."""
        assert len(nominal_result["per_bus_W"]) == len(POWER_BUSES)

    def test_nominal_equals_sum_of_per_bus(self, nominal_result):
        """P_nominal must equal the arithmetic sum of all per-bus powers."""
        assert nominal_result["P_nominal_W"] == pytest.approx(
            sum(nominal_result["per_bus_W"]), rel=1e-12
        )


# ---------------------------------------------------------------------------
# §4 — End-of-Life Power  (document value: 75.81 W)
# ---------------------------------------------------------------------------

class TestEOLPower:
    """§4: P_EOL = P_nominal × (1 + α)"""

    def test_eol_power_matches_document(self, p_eol):
        """P_EOL must equal 75.81 W (document rounds 75.8125 to 75.81)."""
        assert p_eol == pytest.approx(75.81, rel=1e-3), (
            f"Expected P_EOL ≈ 75.81 W, got {p_eol:.6f} W"
        )

    def test_eol_power_exact_arithmetic(self, p_nominal):
        """Verify exact arithmetic: 60.65 × 1.25 = 75.8125 W."""
        result = compute_eol_power(p_nominal, EOL_DEGRADATION_FACTOR)
        assert result == pytest.approx(60.65 * 1.25, rel=1e-12)

    def test_eol_power_greater_than_nominal(self, p_nominal, p_eol):
        """P_EOL must always exceed P_nominal when α > 0."""
        assert p_eol > p_nominal

    def test_eol_within_eps_limit(self, p_eol):
        """§4 compliance: P_EOL must remain below P_EPS_max = 150 W."""
        assert p_eol < EPS_MAX_POWER

    def test_eps_margin_eol_compliant(self, p_eol):
        """compute_power_margin must flag EOL load as compliant."""
        margin = compute_power_margin(EPS_MAX_POWER, p_eol)
        assert margin["compliant"] is True
        assert margin["P_margin_W"] == pytest.approx(EPS_MAX_POWER - p_eol, rel=1e-12)


# ---------------------------------------------------------------------------
# §5 — Excess Solar Power  (document value: 104.19 W)
# ---------------------------------------------------------------------------

class TestExcessSolarPower:
    """§5: P_excess = P_solar − P_EOL"""

    def test_excess_power_matches_document(self, p_excess):
        """P_excess must equal 104.19 W (document rounds 104.1875 to 104.19)."""
        assert p_excess == pytest.approx(104.19, rel=1e-3), (
            f"Expected P_excess ≈ 104.19 W, got {p_excess:.6f} W"
        )

    def test_excess_power_exact_arithmetic(self, p_eol):
        """Verify exact arithmetic: 180 − 75.8125 = 104.1875 W."""
        result = compute_excess_solar_power(SOLAR_ARRAY_POWER, p_eol)
        assert result == pytest.approx(180.0 - 75.8125, rel=1e-12)

    def test_excess_power_positive(self, p_excess):
        """Surplus must be positive — solar exceeds EOL load (§5)."""
        assert p_excess > 0.0

    def test_solar_minus_eol_identity(self, p_eol, p_excess):
        """P_excess + P_EOL must recover P_solar exactly."""
        assert p_excess + p_eol == pytest.approx(SOLAR_ARRAY_POWER, rel=1e-12)


# ---------------------------------------------------------------------------
# §6 — Battery Charging Time  (document value: ≈ 0.32 h / ~19 min)
# ---------------------------------------------------------------------------

class TestChargingTime:
    """§6: t = E_remaining / (η · P_excess)"""

    def test_charging_time_matches_document_hours(self, e_remaining, p_excess):
        """Charging time must be ≈ 0.32 h as stated in §6."""
        t_h = compute_charging_time(e_remaining, p_excess, BATTERY_CHARGING_EFFICIENCY)
        assert t_h == pytest.approx(0.32, abs=0.01), (
            f"Expected t_charge ≈ 0.32 h, got {t_h:.6f} h"
        )

    def test_charging_time_matches_document_minutes(self, e_remaining, p_excess):
        """Charging time must be ≈ 19 minutes as stated in §6."""
        t_h = compute_charging_time(e_remaining, p_excess, BATTERY_CHARGING_EFFICIENCY)
        t_min = t_h * 60
        assert t_min == pytest.approx(19.0, abs=1.0), (
            f"Expected t_charge ≈ 19 min, got {t_min:.3f} min"
        )

    def test_charging_time_exact_formula(self, e_remaining, p_excess):
        """Verify t = E_remaining / (η · P_excess) holds exactly."""
        t_h = compute_charging_time(e_remaining, p_excess, BATTERY_CHARGING_EFFICIENCY)
        expected = e_remaining / (BATTERY_CHARGING_EFFICIENCY * p_excess)
        assert t_h == pytest.approx(expected, rel=1e-12)

    def test_remaining_energy_matches_document(self, e_remaining):
        """E_remaining = 100 × (1 − 0.70) = 30 Wh (§6)."""
        assert e_remaining == pytest.approx(30.0, rel=1e-9)

    def test_charging_time_decreases_with_higher_excess(self, e_remaining):
        """Higher surplus power must reduce charge time (monotonicity)."""
        t_low  = compute_charging_time(e_remaining, 50.0,  BATTERY_CHARGING_EFFICIENCY)
        t_high = compute_charging_time(e_remaining, 200.0, BATTERY_CHARGING_EFFICIENCY)
        assert t_high < t_low

    def test_charging_time_decreases_with_higher_eta(self, e_remaining, p_excess):
        """Higher charging efficiency must reduce charge time (monotonicity)."""
        t_low_eta  = compute_charging_time(e_remaining, p_excess, 0.5)
        t_high_eta = compute_charging_time(e_remaining, p_excess, 1.0)
        assert t_high_eta < t_low_eta


# ---------------------------------------------------------------------------
# Guards — invalid inputs
# ---------------------------------------------------------------------------

class TestInputGuards:
    """Verify that invalid inputs raise ValueError, not silent bad results."""

    def test_negative_excess_raises(self, e_remaining):
        with pytest.raises(ValueError, match="positive"):
            compute_charging_time(e_remaining, -10.0, BATTERY_CHARGING_EFFICIENCY)

    def test_zero_excess_raises(self, e_remaining):
        with pytest.raises(ValueError, match="positive"):
            compute_charging_time(e_remaining, 0.0, BATTERY_CHARGING_EFFICIENCY)

    def test_eta_zero_raises(self, e_remaining, p_excess):
        with pytest.raises(ValueError, match="efficiency"):
            compute_charging_time(e_remaining, p_excess, 0.0)

    def test_soc_above_one_raises(self):
        with pytest.raises(ValueError, match="State of charge"):
            compute_battery_remaining_energy(BATTERY_CAPACITY_WH, 1.01)

    def test_soc_below_zero_raises(self):
        with pytest.raises(ValueError, match="State of charge"):
            compute_battery_remaining_energy(BATTERY_CAPACITY_WH, -0.01)
