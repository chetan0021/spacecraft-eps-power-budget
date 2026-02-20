"""
eps/power_model.py
==================
Spacecraft EPS Power Budget — Pure Mathematical Functions

Implements the symbolic model defined in:
    docs/avionics_power_budget_analysis.md  §2 – §6, §9

Rules:
    - Every function is a pure, deterministic mathematical mapping.
    - No hardcoded results; all output is computed from arguments.
    - No simulation loop, no I/O, no side effects.
    - Equation references are quoted verbatim from the document.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# § 2 — Nominal Electrical Power Consumption
# ---------------------------------------------------------------------------

def compute_nominal_power(buses: list[tuple[float, float]]) -> dict[str, float]:
    """Compute per-bus and total nominal electrical power.

    Equation (§2):
        P_i = V_i · I_i
        P_nominal = Σ P_i

    Args:
        buses: Sequence of (bus_voltage_V, load_current_A) pairs.
               Units — voltage in Volts [V], current in Amperes [A].

    Returns:
        Dictionary with keys:
            ``per_bus_W``   — list[float]: per-bus power [W], same order as input.
            ``P_nominal_W`` — float: total nominal system power [W].

    Example:
        >>> compute_nominal_power([(28.0, 1.2), (12.0, 0.8)])
        {'per_bus_W': [33.6, 9.6], 'P_nominal_W': 43.2}
    """
    per_bus: list[float] = [v * i for v, i in buses]
    p_nominal: float = sum(per_bus)
    return {
        "per_bus_W": per_bus,
        "P_nominal_W": p_nominal,
    }


# ---------------------------------------------------------------------------
# § 4 — End-of-Life Power Consumption
# ---------------------------------------------------------------------------

def compute_eol_power(p_nominal_w: float, alpha: float) -> float:
    """Compute end-of-life avionics power draw after degradation.

    Equation (§4, §9):
        P_EOL = P_nominal · (1 + α)

    Args:
        p_nominal_w: Total nominal system power [W].
        alpha:       Fractional degradation factor (dimensionless).
                     e.g. 0.25 represents 25 % degradation.

    Returns:
        P_EOL — end-of-life power consumption [W].

    Example:
        >>> compute_eol_power(60.65, 0.25)
        75.8125
    """
    return p_nominal_w * (1.0 + alpha)


# ---------------------------------------------------------------------------
# § 3 — EPS Power Margin
# ---------------------------------------------------------------------------

def compute_power_margin(p_eps_max_w: float, p_nominal_w: float) -> dict[str, float | bool]:
    """Compute EPS power margin and compliance against the system load.

    Equation (§3):
        P_margin = P_EPS,max − P_nominal

    Args:
        p_eps_max_w:  Maximum continuous EPS output power [W].
        p_nominal_w:  System power load to evaluate (nominal or EOL) [W].

    Returns:
        Dictionary with keys:
            ``P_margin_W``  — float: available headroom [W]. Negative → overload.
            ``compliant``   — bool: True if load is within EPS capability.

    Example:
        >>> compute_power_margin(150.0, 60.65)
        {'P_margin_W': 89.35, 'compliant': True}
    """
    margin: float = p_eps_max_w - p_nominal_w
    return {
        "P_margin_W": margin,
        "compliant": margin >= 0.0,
    }


# ---------------------------------------------------------------------------
# § 5 — Solar Array Power Balance
# ---------------------------------------------------------------------------

def compute_excess_solar_power(p_solar_w: float, p_eol_w: float) -> float:
    """Compute excess solar power available after satisfying the EOL avionics load.

    Equation (§5, §9):
        P_excess = P_solar − P_EOL

    Args:
        p_solar_w: Solar array generation power [W].
        p_eol_w:   End-of-life avionics power consumption [W].

    Returns:
        P_excess — surplus power available for battery charging and routing [W].
        A negative value indicates a power deficit (eclipse / underperformance).

    Example:
        >>> compute_excess_solar_power(180.0, 75.81)
        104.19
    """
    return p_solar_w - p_eol_w


# ---------------------------------------------------------------------------
# § 6 — Battery Remaining Storage Capacity
# ---------------------------------------------------------------------------

def compute_battery_remaining_energy(e_battery_wh: float, soc: float) -> float:
    """Compute the remaining energy storage headroom in the battery.

    Equation (§6):
        E_remaining = E_battery · (1 − SoC)

    Args:
        e_battery_wh: Total battery pack energy capacity [Wh].
        soc:          Current state of charge as a fraction in [0.0, 1.0].
                      e.g. 0.70 represents 70 % charge.

    Returns:
        E_remaining — energy that can still be stored in the battery [Wh].

    Raises:
        ValueError: If ``soc`` is outside the valid range [0.0, 1.0].

    Example:
        >>> compute_battery_remaining_energy(100.0, 0.70)
        30.0
    """
    if not (0.0 <= soc <= 1.0):
        raise ValueError(
            f"State of charge must be in [0.0, 1.0]; received soc={soc!r}"
        )
    return e_battery_wh * (1.0 - soc)


# ---------------------------------------------------------------------------
# § 6 — Battery Charging Time
# ---------------------------------------------------------------------------

def compute_charging_time(
    e_remaining_wh: float,
    p_excess_w: float,
    eta: float,
) -> float:
    """Compute the time required to fully charge the battery from its current SoC.

    Equations (§6, §9):
        P_charge = P_excess · η
        t        = E_remaining / P_charge
               ≡ E_remaining / (η · P_excess)

    Args:
        e_remaining_wh: Remaining battery storage capacity [Wh].
        p_excess_w:     Excess solar power available for charging [W].
        eta:            Charging energy efficiency (dimensionless, 0.0–1.0).
                        e.g. 0.90 represents 90 % efficiency.

    Returns:
        t_charge_h — time to reach full charge [hours].

    Raises:
        ValueError: If ``eta`` is outside (0.0, 1.0] or ``p_excess_w`` ≤ 0.

    Example:
        >>> compute_charging_time(30.0, 104.19, 0.9)
        0.3199...
    """
    if not (0.0 < eta <= 1.0):
        raise ValueError(
            f"Charging efficiency must be in (0.0, 1.0]; received eta={eta!r}"
        )
    if p_excess_w <= 0.0:
        raise ValueError(
            f"Excess power must be positive for charging; received p_excess_w={p_excess_w!r}"
        )
    p_charge_w: float = p_excess_w * eta
    return e_remaining_wh / p_charge_w
