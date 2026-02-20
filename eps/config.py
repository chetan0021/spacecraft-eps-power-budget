"""
eps/config.py
=============
Spacecraft EPS Power Budget — System Constants

All values are raw engineering constants extracted directly from:
    docs/avionics_power_budget_analysis.md

Rules:
    - No calculations or derived quantities here.
    - All quantities in SI base units (W, A, V, J, dimensionless).
    - Battery capacity is stored in Wh (watt-hours) as the domain standard;
      1 Wh = 3600 J.
    - No simulation logic or conditional expressions.
"""


# ---------------------------------------------------------------------------
# § 2 — Regulated Power Bus Definitions
# ---------------------------------------------------------------------------

# Each entry is a tuple of (bus_voltage_V, load_current_A).
# Buses: 28 V, 12 V, 5 V, 3.3 V regulated rails.
POWER_BUSES: list[tuple[float, float]] = [
    (28.0, 1.2),   # 28 V bus  — ref: §2 Table, row 1
    (12.0, 0.8),   # 12 V bus  — ref: §2 Table, row 2
    (5.0,  2.5),   # 5 V bus   — ref: §2 Table, row 3
    (3.3,  1.5),   # 3.3 V bus — ref: §2 Table, row 4
]

# Individual bus voltages (V)
BUS_VOLTAGE_28V: float = 28.0    # Volts  — ref: §2
BUS_VOLTAGE_12V: float = 12.0    # Volts  — ref: §2
BUS_VOLTAGE_5V:  float = 5.0     # Volts  — ref: §2
BUS_VOLTAGE_3V3: float = 3.3     # Volts  — ref: §2

# Individual bus load currents (A)
BUS_CURRENT_28V: float = 1.2     # Amperes — ref: §2
BUS_CURRENT_12V: float = 0.8     # Amperes — ref: §2
BUS_CURRENT_5V:  float = 2.5     # Amperes — ref: §2
BUS_CURRENT_3V3: float = 1.5     # Amperes — ref: §2


# ---------------------------------------------------------------------------
# § 3 — EPS Capacity Limit
# ---------------------------------------------------------------------------

EPS_MAX_POWER: float = 150.0
"""Maximum continuous EPS output power (W).

Reference: §3 — "Maximum continuous EPS power: P_EPS,max = 150 W"
"""


# ---------------------------------------------------------------------------
# § 4 — End-of-Life Degradation
# ---------------------------------------------------------------------------

EOL_DEGRADATION_FACTOR: float = 0.25
"""Fractional power increase due to end-of-life component degradation (dimensionless).

Represents α in: P_EOL = P_nominal × (1 + α)
Reference: §4 — "Given degradation factor: α = 25% = 0.25"
"""


# ---------------------------------------------------------------------------
# § 5 — Solar Array
# ---------------------------------------------------------------------------

SOLAR_ARRAY_POWER: float = 180.0
"""Rated solar array generation power (W).

Reference: §5 — "Solar array generation: P_solar = 180 W"
"""


# ---------------------------------------------------------------------------
# § 6 — Battery Pack
# ---------------------------------------------------------------------------

BATTERY_CAPACITY_WH: float = 100.0
"""Total battery pack energy capacity (Wh).

Reference: §6 — "Battery capacity: E_battery = 100 Wh"
Note: 1 Wh = 3600 J. Stored in Wh to match domain convention.
"""

BATTERY_INITIAL_SOC: float = 0.70
"""Initial battery state of charge (dimensionless fraction, 0.0–1.0).

Reference: §6 — "State of charge: SoC = 70%"
"""

BATTERY_CHARGING_EFFICIENCY: float = 0.90
"""Coulombic/energy charging efficiency (dimensionless fraction, 0.0–1.0).

Represents η in: P_charge = P_excess × η
Reference: §6 — "Charging efficiency: η = 90% = 0.9"
"""
