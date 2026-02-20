"""
simulation_runner.py
====================
Spacecraft EPS Power Budget — Simulation Runner

Connects all EPS modules in the sequence defined by the engineering document:
    docs/avionics_power_budget_analysis.md  §2 – §9

Execution sequence:
    1. Compute nominal load power          (power_model.compute_nominal_power)
    2. Apply EOL degradation               (power_model.compute_eol_power)
    3. Compute EPS power margin            (power_model.compute_power_margin)
    4. Compute excess solar power          (power_model.compute_excess_solar_power)
    5. Route excess power                  (eps_controller.EPSController.route)
    6. Simulate battery charging over time (battery_model.BatteryModel.simulate)
    7. Print console summary
    8. Plot battery SoC vs time
    9. Print power balance report

Usage:
    python simulation_runner.py
"""

from __future__ import annotations

import sys
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

# EPS modules
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
from eps.battery_model import BatteryModel, BatteryTimeSeries
from eps.eps_controller import EPSController, RoutingAllocation


# ---------------------------------------------------------------------------
# Simulation parameters (not physics — execution configuration only)
# ---------------------------------------------------------------------------

DT_H: float = 1.0 / 60.0        # timestep: 1 minute expressed in hours
DURATION_H: float = 0.5          # simulation window: 30 minutes
SOC_UPPER_LIMIT: float = 1.0     # charge to full (§7)

PLOT_OUTPUT_FILE: str = "battery_soc_vs_time.png"


# ---------------------------------------------------------------------------
# Step 1–4: Static power calculations
# ---------------------------------------------------------------------------

def run_power_calculations() -> dict:
    """Execute the static power budget equations from §2–§5."""

    # § 2 — Nominal power
    nominal = compute_nominal_power(POWER_BUSES)
    p_nominal = nominal["P_nominal_W"]

    # § 4 — EOL power
    p_eol = compute_eol_power(p_nominal, EOL_DEGRADATION_FACTOR)

    # § 3 — EPS margin against nominal and EOL
    margin_nominal = compute_power_margin(EPS_MAX_POWER, p_nominal)
    margin_eol     = compute_power_margin(EPS_MAX_POWER, p_eol)

    # § 5 — Solar excess
    p_excess = compute_excess_solar_power(SOLAR_ARRAY_POWER, p_eol)

    # § 6 — Battery remaining capacity and analytical charge time
    e_remaining = compute_battery_remaining_energy(BATTERY_CAPACITY_WH, BATTERY_INITIAL_SOC)
    t_charge_h  = compute_charging_time(e_remaining, p_excess, BATTERY_CHARGING_EFFICIENCY)

    return {
        "per_bus_W":         nominal["per_bus_W"],
        "P_nominal_W":       p_nominal,
        "P_EOL_W":           p_eol,
        "margin_nominal":    margin_nominal,
        "margin_eol":        margin_eol,
        "P_solar_W":         SOLAR_ARRAY_POWER,
        "P_excess_W":        p_excess,
        "E_remaining_Wh":    e_remaining,
        "t_charge_h":        t_charge_h,
    }


# ---------------------------------------------------------------------------
# Step 5: EPS routing (single-step, at initial SoC)
# ---------------------------------------------------------------------------

def run_routing(p_excess_w: float, current_soc: float) -> RoutingAllocation:
    """Apply §7 four-priority routing for the initial excess power."""
    controller = EPSController(soc_upper_limit=SOC_UPPER_LIMIT)
    return controller.route(p_excess_w=p_excess_w, current_soc=current_soc)


# ---------------------------------------------------------------------------
# Step 6: Battery time simulation
# ---------------------------------------------------------------------------

def run_battery_simulation(p_excess_w: float) -> BatteryTimeSeries:
    """Run forward Euler battery integration over DURATION_H."""
    model = BatteryModel(
        capacity_wh=BATTERY_CAPACITY_WH,
        initial_soc=BATTERY_INITIAL_SOC,
        eta=BATTERY_CHARGING_EFFICIENCY,
    )
    return model.simulate(
        p_excess_w=p_excess_w,
        dt_h=DT_H,
        duration_h=DURATION_H,
    )


# ---------------------------------------------------------------------------
# Step 7: Console summary
# ---------------------------------------------------------------------------

def print_console_summary(power: dict, routing: RoutingAllocation, ts: BatteryTimeSeries) -> None:
    """Print a structured console summary of all computed results."""

    sep = "─" * 60

    print(f"\n{'═' * 60}")
    print("  SPACECRAFT EPS POWER BUDGET — SIMULATION SUMMARY")
    print(f"{'═' * 60}")

    # --- Power buses ---
    print(f"\n{sep}")
    print("  §2  NOMINAL LOAD BREAKDOWN")
    print(sep)
    bus_labels = ["28 V", "12 V", " 5 V", "3.3 V"]
    for label, (v, i), p in zip(bus_labels, POWER_BUSES, power["per_bus_W"]):
        print(f"    Bus {label}:  {v:5.1f} V × {i:.1f} A  =  {p:6.3f} W")
    print(f"    {'─'*44}")
    print(f"    Total nominal load          :  {power['P_nominal_W']:7.3f} W")

    # --- EOL ---
    print(f"\n{sep}")
    print("  §4  END-OF-LIFE POWER")
    print(sep)
    print(f"    Degradation factor  α       :  {EOL_DEGRADATION_FACTOR:.0%}")
    print(f"    P_EOL = P_nominal × (1 + α) :  {power['P_EOL_W']:7.3f} W")

    # --- EPS Margin ---
    print(f"\n{sep}")
    print("  §3  EPS POWER MARGIN")
    print(sep)
    print(f"    EPS max continuous          :  {EPS_MAX_POWER:7.1f} W")
    print(f"    Margin (vs nominal)         :  {power['margin_nominal']['P_margin_W']:7.3f} W  "
          f"[{'✔ COMPLIANT' if power['margin_nominal']['compliant'] else '✘ OVERLOAD'}]")
    print(f"    Margin (vs EOL)             :  {power['margin_eol']['P_margin_W']:7.3f} W  "
          f"[{'✔ COMPLIANT' if power['margin_eol']['compliant'] else '✘ OVERLOAD'}]")

    # --- Solar ---
    print(f"\n{sep}")
    print("  §5  SOLAR POWER BALANCE")
    print(sep)
    print(f"    Solar array generation      :  {power['P_solar_W']:7.1f} W")
    print(f"    P_excess = P_solar − P_EOL  :  {power['P_excess_W']:7.3f} W")

    # --- Battery ---
    print(f"\n{sep}")
    print("  §6  BATTERY STATE")
    print(sep)
    print(f"    Capacity                    :  {BATTERY_CAPACITY_WH:7.1f} Wh")
    print(f"    Initial SoC                 :  {BATTERY_INITIAL_SOC:.0%}")
    print(f"    Remaining capacity          :  {power['E_remaining_Wh']:7.3f} Wh")
    print(f"    Charging efficiency  η      :  {BATTERY_CHARGING_EFFICIENCY:.0%}")
    print(f"    Analytical charge time      :  {power['t_charge_h'] * 60:.2f} min  "
          f"({power['t_charge_h']:.4f} h)")

    # --- Routing ---
    print(f"\n{sep}")
    print("  §7  EPS ROUTING ALLOCATION  (initial step)")
    print(sep)
    print(f"    Available surplus           :  {routing.p_excess_w:7.3f} W")
    print(f"    → Battery charging          :  {routing.battery_charge_w:7.3f} W")
    print(f"    → Payload sharing           :  {routing.payload_w:7.3f} W  [placeholder]")
    print(f"    → Supercapacitor            :  {routing.supercap_w:7.3f} W  [placeholder]")
    print(f"    → Shunt dissipation         :  {routing.shunt_w:7.3f} W")
    print(f"    Battery at SoC limit?       :  {'Yes' if routing.battery_full else 'No'}")

    # --- Simulation result ---
    final = ts.steps[-1]
    print(f"\n{sep}")
    print(f"  SIMULATION RESULT  (Euler, dt = {DT_H * 60:.1f} min, T = {DURATION_H * 60:.0f} min)")
    print(sep)
    print(f"    Steps recorded              :  {len(ts.steps)}")
    print(f"    Final stored energy         :  {final.energy_wh:7.3f} Wh")
    print(f"    Final SoC                   :  {final.soc:.2%}")
    print(f"{'═' * 60}\n")


# ---------------------------------------------------------------------------
# Step 8: Plot — Battery SoC vs Time
# ---------------------------------------------------------------------------

def plot_soc_vs_time(ts: BatteryTimeSeries, analytical_t_h: float) -> None:
    """Render and save battery SoC vs simulation time."""

    times_min  = [s.time_h * 60 for s in ts.steps]
    soc_pct    = [s.soc * 100   for s in ts.steps]
    energy_wh  = [s.energy_wh   for s in ts.steps]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    fig.suptitle(
        "Spacecraft EPS — Battery Charging Simulation\n"
        f"P_excess = {ts.p_excess_w:.2f} W  |  η = {ts.eta:.0%}  |  "
        f"dt = {ts.dt_h * 60:.1f} min  |  Euler Integration",
        fontsize=12, fontweight="bold",
    )

    # ── SoC subplot ──────────────────────────────────────────────────────
    ax1.plot(times_min, soc_pct, color="#2196F3", linewidth=2, label="SoC (simulated)")
    ax1.axhline(100, color="#F44336", linewidth=1.2, linestyle="--", label="100% SoC limit")
    ax1.axhline(BATTERY_INITIAL_SOC * 100, color="#9E9E9E",
                linewidth=1.0, linestyle=":", label=f"Initial SoC ({BATTERY_INITIAL_SOC:.0%})")

    # Annotate analytical charge time
    ax1.axvline(analytical_t_h * 60, color="#FF9800", linewidth=1.2,
                linestyle="-.", label=f"Analytical t_charge ({analytical_t_h * 60:.1f} min)")

    ax1.set_ylabel("State of Charge [%]", fontsize=11)
    ax1.set_ylim(0, 110)
    ax1.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=100))
    ax1.legend(fontsize=9, loc="lower right")
    ax1.grid(True, linestyle="--", alpha=0.5)

    # ── Energy subplot ───────────────────────────────────────────────────
    ax2.plot(times_min, energy_wh, color="#4CAF50", linewidth=2, label="Stored energy")
    ax2.axhline(BATTERY_CAPACITY_WH, color="#F44336", linewidth=1.2,
                linestyle="--", label=f"Capacity ({BATTERY_CAPACITY_WH:.0f} Wh)")
    ax2.axhline(BATTERY_INITIAL_SOC * BATTERY_CAPACITY_WH, color="#9E9E9E",
                linewidth=1.0, linestyle=":",
                label=f"Initial energy ({BATTERY_INITIAL_SOC * BATTERY_CAPACITY_WH:.0f} Wh)")

    ax2.set_xlabel("Simulation Time [minutes]", fontsize=11)
    ax2.set_ylabel("Stored Energy [Wh]", fontsize=11)
    ax2.set_ylim(0, BATTERY_CAPACITY_WH * 1.1)
    ax2.legend(fontsize=9, loc="lower right")
    ax2.grid(True, linestyle="--", alpha=0.5)

    plt.tight_layout()
    plt.savefig(PLOT_OUTPUT_FILE, dpi=150, bbox_inches="tight")
    print(f"  [plot] Saved → {PLOT_OUTPUT_FILE}")
    plt.show()


# ---------------------------------------------------------------------------
# Step 9: Power balance report
# ---------------------------------------------------------------------------

def print_power_balance_report(power: dict, routing: RoutingAllocation) -> None:
    """Print a concise tabular power balance report."""

    sep = "─" * 60
    print(f"\n{'═' * 60}")
    print("  EPS POWER BALANCE REPORT")
    print(f"{'═' * 60}")
    print(f"  {'Parameter':<35} {'Value':>10}  {'Unit':<6}")
    print(sep)

    rows = [
        ("Solar generation",           power["P_solar_W"],                    "W"),
        ("Nominal avionics load",       power["P_nominal_W"],                  "W"),
        ("EOL avionics load",           power["P_EOL_W"],                      "W"),
        ("EPS headroom (vs EOL)",       power["margin_eol"]["P_margin_W"],     "W"),
        ("Excess solar power",          power["P_excess_W"],                   "W"),
        ("→  Battery charging",         routing.battery_charge_w,              "W"),
        ("→  Payload sharing",          routing.payload_w,                     "W"),
        ("→  Supercapacitor",           routing.supercap_w,                    "W"),
        ("→  Shunt dissipation",        routing.shunt_w,                       "W"),
        ("Battery capacity",            BATTERY_CAPACITY_WH,                   "Wh"),
        ("Battery initial SoC",         BATTERY_INITIAL_SOC * 100,             "%"),
        ("Remaining storage capacity",  power["E_remaining_Wh"],               "Wh"),
        ("Analytical charge time",      power["t_charge_h"] * 60,              "min"),
    ]

    for label, value, unit in rows:
        print(f"  {label:<35} {value:>10.3f}  {unit:<6}")

    compliance_nom = "✔" if power["margin_nominal"]["compliant"] else "✘"
    compliance_eol = "✔" if power["margin_eol"]["compliant"] else "✘"
    print(sep)
    print(f"  EPS compliance (nominal)        {compliance_nom}")
    print(f"  EPS compliance (EOL)            {compliance_eol}")
    print(f"{'═' * 60}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("\nInitialising EPS simulation...", flush=True)

    # Steps 1–4: static power equations
    power = run_power_calculations()

    # Step 5: EPS routing at initial state
    routing = run_routing(
        p_excess_w=power["P_excess_W"],
        current_soc=BATTERY_INITIAL_SOC,
    )

    # Step 6: battery time-domain simulation
    # Charging power routed to the battery is P_excess (pre-η); η is applied
    # internally by BatteryModel as per dE/dt = η · P_excess (§9)
    ts = run_battery_simulation(p_excess_w=power["P_excess_W"])

    # Step 7: console summary
    print_console_summary(power, routing, ts)

    # Step 9: power balance report
    print_power_balance_report(power, routing)

    # Step 8: plot (last — opens window / saves file)
    plot_soc_vs_time(ts, analytical_t_h=power["t_charge_h"])


if __name__ == "__main__":
    main()
