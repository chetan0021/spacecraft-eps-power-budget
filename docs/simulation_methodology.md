# Simulation Methodology

**Document type:** Simulation methodology reference
**Primary source:** [`avionics_power_budget_analysis.md`](avionics_power_budget_analysis.md)

---

## 1. Simulation Objective

The simulation reproduces the analytical power budget defined in §2–§9 of the engineering reference document as a time-stepped numerical model. Its purpose is to:

- Compute and verify all static power quantities (nominal, EOL, margin, excess)
- Propagate battery state over time under defined charging conditions
- Confirm that numerically integrated results converge to the analytical charging time

---

## 2. Mathematical Model Description

All equations are reproduced verbatim from the engineering reference document. No equations are derived or extended beyond those stated.

### Nominal load power (§2)

```
P_i      = V_i · I_i
P_nominal = Σ P_i
```

### End-of-life power (§4)

```
P_EOL = P_nominal · (1 + α)
```

Where `α = 0.25` is the defined degradation factor.

### EPS power margin (§3)

```
P_margin = P_EPS,max − P_nominal
```

`P_EPS,max = 150 W`

### Solar power balance (§5)

```
P_excess = P_solar − P_EOL
```

`P_solar = 180 W`

### Battery remaining capacity (§6)

```
E_remaining = E_battery · (1 − SoC)
```

### Effective charging power (§6)

```
P_charge = P_excess · η
```

`η = 0.90`

### Analytical charging time (§6)

```
t = E_remaining / P_charge
  = E_remaining / (η · P_excess)
```

### Battery state ODE (§9)

```
dE/dt = η · P_excess
```

This is the governing differential equation integrated numerically.

---

## 3. Numerical Integration Method

**Method:** Forward Euler (explicit, fixed timestep)

The continuous ODE `dE/dt = η · P_excess` is discretised as:

```
E[n+1] = E[n] + η · P_excess · dt
```

Where `dt` is the fixed timestep in hours.

**Energy bounds enforcement:** At each step, the battery energy is clamped to the interval `[0, E_battery]` to enforce physical constraints:

```
E[n+1] = clamp(E[n] + ΔE,  0,  E_battery)
```

**Timestep:** The reference implementation uses `dt = 1 minute = 1/60 hour`.

**Simulation window:** 30 minutes (`duration = 0.5 h`).

---

## 4. State Variables

| Variable | Symbol | Units | Description |
|---|---|---|---|
| Battery energy | `E` | Wh | Stored energy in battery pack |
| State of charge | `SoC` | fraction [0–1] | `E / E_battery` |
| Time | `t` | h | Simulation clock |
| Charging power | `P_charge` | W | Power delivered to battery this step |
| Shunt power | `P_shunt` | W | Residual power sent to shunt |

All other quantities (`P_nominal`, `P_EOL`, `P_excess`) are time-invariant in the current simulation and computed once before the integration loop.

---

## 5. Assumptions

The following assumptions apply to this simulation, consistent with the reference document scope:

| # | Assumption |
|---|---|
| A1 | Solar array output is constant at 180 W (no orbital eclipse modelled) |
| A2 | Avionics load is constant at `P_EOL` for the simulation duration |
| A3 | Charging efficiency `η` is constant and independent of SoC or temperature |
| A4 | Battery capacity is fixed; no capacity fade is modelled |
| A5 | No temperature effects on battery or solar performance are included |
| A6 | No nonlinear battery voltage–SoC relationship is modelled |
| A7 | No payload power demand is active (Priority 2 sink carries 0 W) |
| A8 | No supercapacitor model is active (Priority 3 sink carries 0 W) |

---

## 6. Verification Approach

Simulation outputs are verified against the four numerical targets stated in the reference document:

| Quantity | Document value | Verification tolerance |
|---|---|---|
| `P_nominal` | 60.65 W | `rel = 1 × 10⁻⁴` |
| `P_EOL` | 75.81 W | `rel = 1 × 10⁻³` |
| `P_excess` | 104.19 W | `rel = 1 × 10⁻³` |
| `t_charge` | ≈ 0.32 h (~19 min) | `abs = 0.01 h` |

Tolerances are set to accept the true floating-point arithmetic result while rejecting values that deviate from the document rounded figures by more than the document's own rounding error.

Verification is executed via the pytest suite at:

```
tests/test_power_calculations.py
```

Run with:

```powershell
pytest tests/test_power_calculations.py -v
```

---

## 7. Expected Outputs

### Console output

- Per-bus power breakdown (§2)
- EOL power and compliance flag (§4)
- EPS power margin at nominal and EOL (§3)
- Solar excess power (§5)
- Battery remaining capacity and analytical charge time (§6)
- §7 routing allocation at initial timestep
- Final simulated battery energy and SoC

### Tabular report

Power balance report listing all quantities with values and SI units.

### Plots

| Plot | Content | File |
|---|---|---|
| Battery SoC vs time | Simulated SoC with analytical charge time marker | `battery_soc_vs_time.png` |
| Full power flow | Solar, avionics, charging, and shunt power vs time | `eps_power_flow.png` |
| Battery energy vs time | Stored energy [Wh] vs simulation time | `eps_power_flow.png` (subplot) |
| Battery SoC (flow sim) | SoC [%] vs simulation time | `eps_power_flow.png` (subplot) |
