"""
eps/battery_model.py
====================
Spacecraft EPS Power Budget — Time-Based Battery Energy Model

Implements Euler integration of the battery state equation defined in:
    docs/avionics_power_budget_analysis.md  §6, §9

Governing equation (§9):
    dE/dt = η · P_excess

Integration method: Forward Euler (explicit, fixed timestep)
    E(t + dt) = E(t) + η · P_excess · dt

Scope:
    - Linear charging/discharging dynamics only.
    - No temperature model, no nonlinear capacity fade, no C-rate effects.
    - Energy is clamped to [0, E_capacity] to respect physical bounds.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class BatteryState:
    """Snapshot of battery state at a single timestep.

    Attributes:
        time_h:       Simulation time at this step [hours].
        energy_wh:    Stored energy in the battery at this step [Wh].
        soc:          State of charge as a fraction [0.0, 1.0].
        delta_e_wh:   Energy increment applied this step [Wh].
                      Positive = charging, negative = discharging.
    """
    time_h:     float
    energy_wh:  float
    soc:        float
    delta_e_wh: float


@dataclass
class BatteryTimeSeries:
    """Complete time-series result from a battery simulation run.

    Attributes:
        steps:          Ordered list of BatteryState snapshots.
        dt_h:           Fixed timestep used [hours].
        duration_h:     Total simulated duration [hours].
        capacity_wh:    Battery energy capacity [Wh].
        eta:            Charging efficiency used [dimensionless].
        p_excess_w:     Excess power supplied throughout [W].
    """
    steps:       list[BatteryState] = field(default_factory=list)
    dt_h:        float = 0.0
    duration_h:  float = 0.0
    capacity_wh: float = 0.0
    eta:         float = 0.0
    p_excess_w:  float = 0.0


# ---------------------------------------------------------------------------
# Battery model
# ---------------------------------------------------------------------------

class BatteryModel:
    """Time-based battery energy model using forward Euler integration.

    Integrates the document's governing ODE over a fixed timestep grid:

        dE/dt = η · P_excess          (§9)

    Euler step:
        E[n+1] = E[n] + η · P_excess · dt

    Energy is clamped to [0, capacity_wh] at every step to enforce
    the physical battery bounds (full / empty).

    Args:
        capacity_wh:     Total battery energy capacity [Wh].
        initial_soc:     Initial state of charge, fraction in [0.0, 1.0].
        eta:             Charging efficiency (dimensionless, (0.0, 1.0]).
                         Applied symmetrically: charging losses reduce
                         stored energy; discharging losses are not
                         separately modelled per the document scope.

    Raises:
        ValueError: If any constructor argument is outside its valid range.
    """

    def __init__(
        self,
        capacity_wh: float,
        initial_soc: float,
        eta: float,
    ) -> None:
        if capacity_wh <= 0.0:
            raise ValueError(
                f"Battery capacity must be positive; received capacity_wh={capacity_wh!r}"
            )
        if not (0.0 <= initial_soc <= 1.0):
            raise ValueError(
                f"Initial SoC must be in [0.0, 1.0]; received initial_soc={initial_soc!r}"
            )
        if not (0.0 < eta <= 1.0):
            raise ValueError(
                f"Charging efficiency must be in (0.0, 1.0]; received eta={eta!r}"
            )

        self._capacity_wh: float = capacity_wh
        self._eta: float = eta
        self._initial_energy_wh: float = initial_soc * capacity_wh

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def simulate(
        self,
        p_excess_w: float,
        dt_h: float,
        duration_h: float,
    ) -> BatteryTimeSeries:
        """Run forward Euler integration over [0, duration_h].

        At each timestep n:
            ΔE = η · P_excess · dt        (energy increment [Wh])
            E[n+1] = clamp(E[n] + ΔE,  0,  capacity_wh)

        Args:
            p_excess_w:  Constant excess power driving the battery [W].
                         Positive → charging; negative → discharging.
                         Units: Watts [W].
            dt_h:        Fixed integration timestep [hours].
                         Must be positive and ≤ duration_h.
            duration_h:  Total simulation window [hours].
                         Must be positive.

        Returns:
            BatteryTimeSeries containing one BatteryState per timestep,
            including t=0 (initial condition).

        Raises:
            ValueError: If dt_h or duration_h are non-positive, or
                        dt_h > duration_h.

        Example:
            >>> model = BatteryModel(
            ...     capacity_wh=100.0,
            ...     initial_soc=0.70,
            ...     eta=0.90,
            ... )
            >>> result = model.simulate(p_excess_w=104.19, dt_h=1/60, duration_h=0.5)
            >>> result.steps[0].energy_wh
            70.0
            >>> result.steps[0].soc
            0.7
        """
        if dt_h <= 0.0:
            raise ValueError(
                f"Timestep must be positive; received dt_h={dt_h!r}"
            )
        if duration_h <= 0.0:
            raise ValueError(
                f"Duration must be positive; received duration_h={duration_h!r}"
            )
        if dt_h > duration_h:
            raise ValueError(
                f"Timestep dt_h={dt_h!r} exceeds duration_h={duration_h!r}"
            )

        result = BatteryTimeSeries(
            dt_h=dt_h,
            duration_h=duration_h,
            capacity_wh=self._capacity_wh,
            eta=self._eta,
            p_excess_w=p_excess_w,
        )

        energy_wh: float = self._initial_energy_wh
        time_h: float = 0.0

        # Record initial condition (step 0)
        result.steps.append(
            BatteryState(
                time_h=time_h,
                energy_wh=energy_wh,
                soc=self._to_soc(energy_wh),
                delta_e_wh=0.0,
            )
        )

        # Forward Euler integration loop
        # Governing equation (§9): dE/dt = η · P_excess
        n_steps: int = int(duration_h / dt_h)
        for _ in range(n_steps):
            delta_e: float = self._eta * p_excess_w * dt_h   # ΔE = η · P_excess · dt
            new_energy: float = self._clamp(energy_wh + delta_e)
            time_h += dt_h
            energy_wh = new_energy

            result.steps.append(
                BatteryState(
                    time_h=round(time_h, 10),   # avoid floating-point drift in labels
                    energy_wh=energy_wh,
                    soc=self._to_soc(energy_wh),
                    delta_e_wh=delta_e,
                )
            )

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _to_soc(self, energy_wh: float) -> float:
        """Convert stored energy to state-of-charge fraction."""
        return energy_wh / self._capacity_wh

    def _clamp(self, energy_wh: float) -> float:
        """Enforce physical energy bounds [0, capacity_wh]."""
        return max(0.0, min(self._capacity_wh, energy_wh))
