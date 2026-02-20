"""
eps_power_flow_simulation.py
============================
Spacecraft EPS — Full Power Flow Simulation

Models the complete spacecraft EPS power flow at each timestep using ONLY
equations, values, and routing priorities defined in:
    docs/avionics_power_budget_analysis.md

Power flow path (§7):
    Solar Array → EPS → [Avionics Load] → Battery → Shunt

Routing priority per timestep (§7):
    1. Supply avionics EOL load from solar
    2. Charge battery from remaining surplus (until capacity limit)
    3. Route residual to shunt dissipation

Governing equation for battery state (§9):
    dE/dt = η · P_excess        (Forward Euler integration)

No new physics, no new parameters, no optimisation logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

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
    compute_excess_solar_power,
)


# ---------------------------------------------------------------------------
# Simulation configuration (execution parameters — not physics)
# ---------------------------------------------------------------------------

DT_H: float = 1.0 / 60.0       # timestep: 1 minute in hours
DURATION_H: float = 0.5         # simulation window: 30 minutes
PLOT_OUTPUT_FILE: str = "eps_power_flow.png"


# ---------------------------------------------------------------------------
# Time-series data container
# ---------------------------------------------------------------------------

@dataclass
class EPSTimeSeries:
    """Complete time-series record for the EPS power flow simulation.

    All power values in Watts [W]. Energy in Wh. SoC as fraction [0.0–1.0].
    Time in hours [h].
    """
    time_h:                 list[float] = field(default_factory=list)
    solar_power_w:          list[float] = field(default_factory=list)
    avionics_power_w:       list[float] = field(default_factory=list)
    battery_charging_w:     list[float] = field(default_factory=list)
    shunt_dissipation_w:    list[float] = field(default_factory=list)
    battery_energy_wh:      list[float] = field(default_factory=list)
    battery_soc:            list[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Static power quantities (computed once from document equations)
# ---------------------------------------------------------------------------

def _compute_static_power() -> tuple[float, float, float]:
    """Compute time-invariant EPS power quantities.

    Returns:
        (p_eol_w, p_excess_w, P_solar_w) — all in Watts.
    """
    nominal = compute_nominal_power(POWER_BUSES)
    p_eol   = compute_eol_power(nominal["P_nominal_W"], EOL_DEGRADATION_FACTOR)
    p_excess = compute_excess_solar_power(SOLAR_ARRAY_POWER, p_eol)
    return p_eol, p_excess, SOLAR_ARRAY_POWER


# ---------------------------------------------------------------------------
# Single-step routing (§7 priority cascade)
# ---------------------------------------------------------------------------

def _route_step(
    p_solar_w: float,
    p_avionics_w: float,
    battery_energy_wh: float,
    eta: float,
    capacity_wh: float,
    dt_h: float,
) -> tuple[float, float, float, float]:
    """Apply §7 routing for one timestep.

    Priority order:
        1. Supply avionics EOL load
        2. Charge battery from surplus (capped by remaining capacity)
        3. Route unused surplus to shunt dissipation

    Battery energy update (§9):
        ΔE = η · P_charge_routed · dt
        E[n+1] = clamp(E[n] + ΔE, 0, capacity_wh)

    Args:
        p_solar_w:          Solar generation this step [W].
        p_avionics_w:       Avionics EOL load this step [W].
        battery_energy_wh:  Current stored battery energy [Wh].
        eta:                Charging efficiency (dimensionless).
        capacity_wh:        Battery capacity [Wh].
        dt_h:               Timestep [hours].

    Returns:
        Tuple of (battery_charging_w, shunt_w, new_battery_energy_wh, p_excess_w).
    """
    # Step 1 — avionics load is served directly from solar (or logged as deficit)
    p_excess = p_solar_w - p_avionics_w     # P_excess = P_solar − P_EOL  (§5, §9)
    remaining = max(p_excess, 0.0)          # no negative routing — deficit handled separately

    # Step 2 — battery charging (§7 rule 2)
    # Maximum energy that can still be stored
    e_headroom_wh = capacity_wh - battery_energy_wh
    # Maximum power that would fill headroom within this timestep
    p_charge_max = e_headroom_wh / (eta * dt_h) if dt_h > 0 else 0.0
    battery_charging_w = min(remaining, p_charge_max)
    remaining -= battery_charging_w

    # Step 3 — shunt dissipation: absorbs everything left (§7 rule 4 / §8)
    shunt_w = remaining

    # Battery energy update: dE/dt = η · P_charge  →  ΔE = η · P_charge · dt  (§9)
    delta_e = eta * battery_charging_w * dt_h
    new_energy = min(max(battery_energy_wh + delta_e, 0.0), capacity_wh)

    return battery_charging_w, shunt_w, new_energy, p_excess


# ---------------------------------------------------------------------------
# Simulation loop
# ---------------------------------------------------------------------------

def run_simulation() -> EPSTimeSeries:
    """Execute the full EPS power flow simulation.

    Computes static quantities once, then steps forward in time using
    forward Euler integration and the §7 routing priority cascade.

    Returns:
        EPSTimeSeries containing one record per timestep including t = 0.
    """
    p_eol, _p_excess_analytical, p_solar = _compute_static_power()

    ts = EPSTimeSeries()
    battery_energy = BATTERY_INITIAL_SOC * BATTERY_CAPACITY_WH
    time_h = 0.0
    n_steps = int(DURATION_H / DT_H)

    # Record initial condition (step 0)
    ts.time_h.append(0.0)
    ts.solar_power_w.append(p_solar)
    ts.avionics_power_w.append(p_eol)
    ts.battery_charging_w.append(0.0)
    ts.shunt_dissipation_w.append(0.0)
    ts.battery_energy_wh.append(battery_energy)
    ts.battery_soc.append(battery_energy / BATTERY_CAPACITY_WH)

    for _ in range(n_steps):
        charging_w, shunt_w, battery_energy, _ = _route_step(
            p_solar_w=p_solar,
            p_avionics_w=p_eol,
            battery_energy_wh=battery_energy,
            eta=BATTERY_CHARGING_EFFICIENCY,
            capacity_wh=BATTERY_CAPACITY_WH,
            dt_h=DT_H,
        )
        time_h += DT_H

        ts.time_h.append(round(time_h, 10))
        ts.solar_power_w.append(p_solar)
        ts.avionics_power_w.append(p_eol)
        ts.battery_charging_w.append(charging_w)
        ts.shunt_dissipation_w.append(shunt_w)
        ts.battery_energy_wh.append(battery_energy)
        ts.battery_soc.append(battery_energy / BATTERY_CAPACITY_WH)

    return ts


# ---------------------------------------------------------------------------
# Console report
# ---------------------------------------------------------------------------

def print_report(ts: EPSTimeSeries) -> None:
    """Print a concise power flow summary to stdout."""
    sep = "─" * 60
    final = {
        "energy_wh": ts.battery_energy_wh[-1],
        "soc":       ts.battery_soc[-1],
        "charge_w":  ts.battery_charging_w[-1],
        "shunt_w":   ts.shunt_dissipation_w[-1],
    }
    # Find first step where battery is full
    full_step = next(
        (i for i, e in enumerate(ts.battery_energy_wh) if e >= BATTERY_CAPACITY_WH),
        None,
    )
    t_full_min = ts.time_h[full_step] * 60 if full_step is not None else None

    print(f"\n{'═' * 60}")
    print("  EPS POWER FLOW SIMULATION — REPORT")
    print(f"{'═' * 60}")
    print(f"  Simulation window          : {DURATION_H * 60:.0f} min  (dt = {DT_H * 60:.1f} min)")
    print(f"  Steps recorded             : {len(ts.time_h)}")
    print(sep)
    print(f"  Solar generation           : {ts.solar_power_w[0]:7.3f} W  (constant)")
    print(f"  Avionics EOL load          : {ts.avionics_power_w[0]:7.3f} W  (constant)")
    print(f"  Initial battery energy     : {ts.battery_energy_wh[0]:7.3f} Wh  "
          f"({ts.battery_soc[0]:.0%} SoC)")
    print(sep)
    print(f"  Final battery energy       : {final['energy_wh']:7.3f} Wh")
    print(f"  Final battery SoC          : {final['soc']:.2%}")
    print(f"  Final charging power       : {final['charge_w']:7.3f} W")
    print(f"  Final shunt dissipation    : {final['shunt_w']:7.3f} W")
    if t_full_min is not None:
        print(f"  Battery reached full at    : {t_full_min:.2f} min")
    else:
        print(f"  Battery did not reach full within simulation window.")
    print(f"{'═' * 60}\n")


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def plot_results(ts: EPSTimeSeries) -> None:
    """Render and save the three required EPS power flow plots."""

    times_min = [t * 60 for t in ts.time_h]

    fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
    fig.suptitle(
        "Spacecraft EPS — Full Power Flow Simulation\n"
        f"dt = {DT_H * 60:.1f} min  |  Duration = {DURATION_H * 60:.0f} min  |"
        f"  η = {BATTERY_CHARGING_EFFICIENCY:.0%}  |  Forward Euler",
        fontsize=12, fontweight="bold",
    )

    # ── Plot 1: Power Flow vs Time ─────────────────────────────────────
    ax1 = axes[0]
    ax1.plot(times_min, ts.solar_power_w,       color="#FF9800", linewidth=2,
             label=f"Solar generation ({ts.solar_power_w[0]:.1f} W)")
    ax1.plot(times_min, ts.avionics_power_w,    color="#2196F3", linewidth=2,
             linestyle="--", label=f"Avionics EOL load ({ts.avionics_power_w[0]:.2f} W)")
    ax1.plot(times_min, ts.battery_charging_w,  color="#4CAF50", linewidth=2,
             label="Battery charging power (W)")
    ax1.plot(times_min, ts.shunt_dissipation_w, color="#F44336", linewidth=2,
             linestyle="-.", label="Shunt dissipation (W)")

    ax1.set_ylabel("Power [W]", fontsize=11)
    ax1.set_title("Plot 1 — Power Flow vs Time", fontsize=10, loc="left")
    ax1.legend(fontsize=9, loc="right")
    ax1.grid(True, linestyle="--", alpha=0.45)
    ax1.set_ylim(bottom=0)

    # ── Plot 2: Battery Energy vs Time ────────────────────────────────
    ax2 = axes[1]
    ax2.plot(times_min, ts.battery_energy_wh, color="#9C27B0", linewidth=2,
             label="Stored energy (Wh)")
    ax2.axhline(BATTERY_CAPACITY_WH, color="#F44336", linewidth=1.2,
                linestyle="--", label=f"Capacity ({BATTERY_CAPACITY_WH:.0f} Wh)")
    ax2.axhline(BATTERY_INITIAL_SOC * BATTERY_CAPACITY_WH, color="#9E9E9E",
                linewidth=1.0, linestyle=":",
                label=f"Initial energy ({BATTERY_INITIAL_SOC * BATTERY_CAPACITY_WH:.0f} Wh)")

    ax2.set_ylabel("Energy [Wh]", fontsize=11)
    ax2.set_title("Plot 2 — Battery Energy vs Time", fontsize=10, loc="left")
    ax2.set_ylim(0, BATTERY_CAPACITY_WH * 1.12)
    ax2.legend(fontsize=9, loc="lower right")
    ax2.grid(True, linestyle="--", alpha=0.45)

    # ── Plot 3: Battery SoC vs Time ───────────────────────────────────
    ax3 = axes[2]
    ax3.plot(times_min, [s * 100 for s in ts.battery_soc],
             color="#00BCD4", linewidth=2, label="State of Charge (%)")
    ax3.axhline(100, color="#F44336", linewidth=1.2, linestyle="--",
                label="100% SoC limit")
    ax3.axhline(BATTERY_INITIAL_SOC * 100, color="#9E9E9E", linewidth=1.0,
                linestyle=":", label=f"Initial SoC ({BATTERY_INITIAL_SOC:.0%})")

    ax3.set_xlabel("Simulation Time [minutes]", fontsize=11)
    ax3.set_ylabel("State of Charge [%]", fontsize=11)
    ax3.set_title("Plot 3 — Battery SoC vs Time", fontsize=10, loc="left")
    ax3.set_ylim(0, 112)
    ax3.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=100))
    ax3.legend(fontsize=9, loc="lower right")
    ax3.grid(True, linestyle="--", alpha=0.45)

    plt.tight_layout()
    plt.savefig(PLOT_OUTPUT_FILE, dpi=150, bbox_inches="tight")
    print(f"  [plot] Saved → {PLOT_OUTPUT_FILE}")
    plt.show()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("\nRunning EPS power flow simulation...", flush=True)
    ts = run_simulation()
    print_report(ts)
    plot_results(ts)


if __name__ == "__main__":
    main()
