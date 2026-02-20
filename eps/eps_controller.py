"""
eps/eps_controller.py
=====================
Spacecraft EPS Power Budget — Rule-Based Power Routing Controller

Implements the EPS power routing priority strategy defined in:
    docs/avionics_power_budget_analysis.md  §7

Priority order (§7):
    1. Battery charging until safe SoC upper limit
    2. Payload subsystem power sharing      [placeholder — reserved sink]
    3. Supercapacitor buffering for transients [placeholder — reserved sink]
    4. Shunt regulation (thermal dissipation)

Engineering rationale (§7):
    - Maximises energy availability during eclipse
    - Minimises thermal losses
    - Stabilises power bus voltage
    - Preserves battery health

Scope:
    - Deterministic, rule-based decision logic only.
    - No optimisation algorithms, no control theory, no feedback loops.
    - Each call to route() is stateless and idempotent given the same inputs.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class RoutingAllocation:
    """Power allocation across all EPS sinks for a single timestep.

    All values in Watts [W]. The following identity holds:

        battery_charge_w + payload_w + supercap_w + shunt_w == p_excess_w

    (where p_excess_w is the value passed to :func:`EPSController.route`).

    Attributes:
        p_excess_w:       Total excess power available for routing [W].
        battery_charge_w: Power directed to battery charging [W].
        payload_w:        Power directed to payload sharing [W].
                          (Placeholder — value is 0.0 in this release.)
        supercap_w:       Power directed to supercapacitor buffering [W].
                          (Placeholder — value is 0.0 in this release.)
        shunt_w:          Residual power dissipated via shunt regulation [W].
        battery_full:     True if the battery reached the SoC upper limit
                          and charging was curtailed this step.
    """
    p_excess_w:       float
    battery_charge_w: float
    payload_w:        float
    supercap_w:       float
    shunt_w:          float
    battery_full:     bool


# ---------------------------------------------------------------------------
# EPS routing controller
# ---------------------------------------------------------------------------

class EPSController:
    """Rule-based EPS power routing controller.

    Applies the four-priority routing strategy from §7 of the engineering
    document in strict sequential order.  Each call to :meth:`route` is
    fully deterministic and stateless — no internal state is mutated.

    Args:
        soc_upper_limit: SoC fraction at which battery charging is curtailed.
                         Must be in (0.0, 1.0].  Default 1.0 (charge to full).
                         e.g. 0.95 stops charging at 95 % to preserve cell health.

    Raises:
        ValueError: If ``soc_upper_limit`` is outside (0.0, 1.0].
    """

    def __init__(self, soc_upper_limit: float = 1.0) -> None:
        if not (0.0 < soc_upper_limit <= 1.0):
            raise ValueError(
                f"soc_upper_limit must be in (0.0, 1.0]; "
                f"received soc_upper_limit={soc_upper_limit!r}"
            )
        self._soc_upper_limit: float = soc_upper_limit

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(self, p_excess_w: float, current_soc: float) -> RoutingAllocation:
        """Allocate excess solar power across EPS sinks.

        Applies the §7 priority cascade in order:

            1. **Battery charging** — routes as much of the surplus as
               possible to the battery, provided ``current_soc`` is below
               ``soc_upper_limit``.  If the limit is already met, the full
               surplus passes to lower priorities.

            2. **Payload sharing** — placeholder sink.  Reserved for future
               subsystem power-sharing logic.  Consumes 0 W in this release.

            3. **Supercapacitor buffering** — placeholder sink.  Reserved for
               transient load-levelling logic.  Consumes 0 W in this release.

            4. **Shunt regulation** — absorbs all power not claimed by higher
               priorities.  Represents waste heat dissipated thermally (§8).

        If ``p_excess_w`` is zero or negative (deficit / eclipse mode) no
        routing is performed and all sinks receive 0 W.  A negative input
        represents a power deficit; the caller (orchestrator) is responsible
        for handling discharge separately via the battery model.

        Args:
            p_excess_w:   Excess solar power available [W].
                          Positive → surplus; zero/negative → no routing.
            current_soc:  Current battery state of charge, fraction [0.0, 1.0].

        Returns:
            :class:`RoutingAllocation` with per-sink power values [W].

        Raises:
            ValueError: If ``current_soc`` is outside [0.0, 1.0].

        Example:
            >>> ctrl = EPSController(soc_upper_limit=1.0)
            >>> alloc = ctrl.route(p_excess_w=104.19, current_soc=0.70)
            >>> alloc.battery_charge_w   # full surplus to battery (not yet full)
            104.19
            >>> alloc.shunt_w
            0.0
        """
        if not (0.0 <= current_soc <= 1.0):
            raise ValueError(
                f"current_soc must be in [0.0, 1.0]; received current_soc={current_soc!r}"
            )

        # No surplus — nothing to route
        if p_excess_w <= 0.0:
            return RoutingAllocation(
                p_excess_w=p_excess_w,
                battery_charge_w=0.0,
                payload_w=0.0,
                supercap_w=0.0,
                shunt_w=0.0,
                battery_full=(current_soc >= self._soc_upper_limit),
            )

        remaining_w: float = p_excess_w

        # ------------------------------------------------------------------
        # Priority 1 — Battery charging (§7, rule 1)
        # Charge until SoC reaches the safe upper limit.
        # ------------------------------------------------------------------
        battery_full: bool = current_soc >= self._soc_upper_limit
        if battery_full:
            battery_charge_w: float = 0.0
        else:
            battery_charge_w = remaining_w       # route all available surplus
        remaining_w -= battery_charge_w

        # ------------------------------------------------------------------
        # Priority 2 — Payload subsystem power sharing (§7, rule 2)
        # Placeholder: no payload demand model defined yet.
        # ------------------------------------------------------------------
        payload_w: float = 0.0                   # reserved — implement when payload model exists
        remaining_w -= payload_w

        # ------------------------------------------------------------------
        # Priority 3 — Supercapacitor buffering for transients (§7, rule 3)
        # Placeholder: no supercapacitor model defined yet.
        # ------------------------------------------------------------------
        supercap_w: float = 0.0                  # reserved — implement when supercap model exists
        remaining_w -= supercap_w

        # ------------------------------------------------------------------
        # Priority 4 — Shunt regulation / thermal dissipation (§7, rule 4)
        # All unrouted power is dissipated as heat (see §8 thermal implications).
        # ------------------------------------------------------------------
        shunt_w: float = remaining_w             # absorbs everything left over

        return RoutingAllocation(
            p_excess_w=p_excess_w,
            battery_charge_w=battery_charge_w,
            payload_w=payload_w,
            supercap_w=supercap_w,
            shunt_w=shunt_w,
            battery_full=battery_full,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def soc_upper_limit(self) -> float:
        """SoC fraction at which battery charging is curtailed [0.0–1.0]."""
        return self._soc_upper_limit
