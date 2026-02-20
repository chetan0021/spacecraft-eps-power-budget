# Avionics Power Budget Analysis
### Spacecraft Electrical Power System Evaluation

## 1. Problem Definition

A spacecraft avionics system consists of four regulated power buses:

| Bus Voltage | Load Current |
|---|---|
| 28 V | 1.2 A |
| 12 V | 0.8 A |
| 5 V | 2.5 A |
| 3.3 V | 1.5 A |

Objectives:
- Determine nominal and end-of-life power consumption
- Evaluate EPS power margin
- Analyze solar power utilization
- Compute battery charging behavior
- Recommend EPS power routing strategy

---

# 2. Nominal Electrical Power Consumption

Electrical power for each subsystem is:

P_i = V_i · I_i

### Subsystem Power

P_28V = 28 × 1.2 = 33.6 W
P_12V = 12 × 0.8 = 9.6 W
P_5V = 5 × 2.5 = 12.5 W
P_3.3V = 3.3 × 1.5 = 4.95 W

### Total Nominal Power

P_nominal = Σ P_i
P_nominal = 33.6 + 9.6 + 12.5 + 4.95
P_nominal = 60.65 W

---

# 3. EPS Power Margin

Maximum continuous EPS power:

P_EPS,max = 150 W

Power margin:

P_margin = P_EPS,max − P_nominal
P_margin = 150 − 60.65
P_margin = 89.35 W

Result:
The avionics system operates well within EPS capability.

---

# 4. End-of-Life Power Consumption

Given degradation factor:

α = 25% = 0.25

P_EOL = P_nominal (1 + α)
P_EOL = 60.65 × 1.25
P_EOL = 75.81 W

EPS Compliance Check:

75.81 < 150

Result:
The avionics system remains within the EPS power budget at end of life.

---

# 5. Solar Array Power Balance

Solar array generation:

P_solar = 180 W

Excess power after avionics load:

P_excess = P_solar − P_EOL
P_excess = 180 − 75.81
P_excess = 104.19 W

Result:
The spacecraft must manage a large continuous power surplus.

---

# 6. Battery Charging Analysis

Battery capacity:

E_battery = 100 Wh

State of charge:

SoC = 70%

Remaining storage capacity:

E_remaining = E_battery (1 − SoC)
E_remaining = 100 × 0.3
E_remaining = 30 Wh

Charging efficiency:

η = 90% = 0.9

Effective charging power:

P_charge = P_excess · η
P_charge = 104.19 × 0.9
P_charge = 93.77 W

Charging time:

 t = E_remaining / P_charge
 t = 30 / 93.77
 t = 0.32 hours
 t ≈ 19 minutes

Result:
Battery can be fully charged rapidly using excess solar power.

---

# 7. EPS Power Routing Strategy

Recommended Priority:

1. Battery charging until safe SoC limit
2. Payload subsystem power sharing
3. Supercapacitor buffering for transients
4. Shunt regulation (thermal dissipation)

Engineering Rationale:

- Maximizes energy availability during eclipse
- Minimizes thermal losses
- Stabilizes power bus voltage
- Preserves battery health

---

# 8. System-Level Implications

## Thermal Control
Unutilized power dissipated via shunt regulation converts to heat:

Q = P_excess

Large thermal loads increase radiator sizing requirements and risk overheating.

## Battery Lifetime
Improper charge control causes:
- Accelerated capacity degradation
- Thermal stress
- Reduced cycle life

## Power Bus Stability
Poor regulation can cause:
- Bus overvoltage
- Converter stress
- Avionics malfunction or latch-up

---

# 9. Symbolic Model for Simulation

Define:

P_total = Σ V_i I_i

P_EOL = P_total (1 + α)

P_excess = P_solar − P_EOL

Battery state evolution:

dE/dt = η P_excess

Charging time:

t = E_remaining / (η P_excess)

These equations form the basis of the Python simulation model.

---

# 10. Key Engineering Conclusions

✔ Nominal avionics load = 60.65 W
✔ End-of-life load = 75.81 W
✔ EPS margin is sufficient
✔ Large solar power surplus exists
✔ Energy storage should be prioritized
✔ Proper EPS regulation is mission-critical

