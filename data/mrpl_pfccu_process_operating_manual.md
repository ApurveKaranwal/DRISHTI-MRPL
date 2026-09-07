# Mangalore Refinery and Petrochemicals Limited (MRPL)
## Technical Operating Manual: Petrochemical Fluidized Catalytic Cracking Unit (PFCCU) & Propylene Recovery Unit (PRU)

**Document Reference:** MRPL/TECH/OP-MAN/PFCCU-430-REV3  
**Unit Identification:** Unit 430 (PFCCU) & Unit 440 (PRU / PP Complex)  
**Nominal Processing Capacity:** 2.20 MMTPA (275.0 t/h fresh feed design)  
**Licensor Technology:** High-Severity Deep Catalytic Cracking with Selective Hydrogenation & C3 Splitter Fractionation  
**Governing Standards:** OISD-STD-129, API RP 551, ASTM D5234 (Polymer-Grade Propylene Specification)

---

### 1. Process Overview & Unit Architecture

MRPL Phase-III operates an advanced Petrochemical Fluidized Catalytic Cracking Unit (PFCCU) specifically configured for maximum light olefin (propylene, C3=) selectivity rather than conventional transportation fuel production. The unit converts heavy vacuum gas oils and residue streams into high-octane blend components, liquefied petroleum gas, and a dedicated petrochemical-grade C3 cut.

The C3 stream from the PFCCU main fractionation and gas concentration section is routed directly to the integrated Propylene Recovery Unit (PRU), which purifies the cracked stream into Polymer-Grade Propylene (PGP) used as feedstock for MRPLs 440 KTPA Polypropylene (PP) Plant.

#### Primary Feedstock Envelope:
- **Hydrotreated Heavy Vacuum Gas Oil (HVGO)**: 65–75 wt%
- **Hydrocracker Unconverted Oil (HCU-UCO)**: 15–25 wt%
- **Deasphalted Oil (DAO) / Treated Atmospheric Residue**: 5–15 wt%
- **Feed API Gravity**: 22.5 – 26.8° API
- **Feed Total ConCarbon (CCR)**: 0.8 – 2.2 wt%

---

### 2. Operating Coil & Riser Temperature Profiles

In high-severity PFCCU operation, the riser outlet temperature (ROT) and feed coil outlet temperatures dictate cracking reaction kinetics, thermal cracking contribution, and olefin selectivity:

| Operating Parameter | Normal Baseline Mode | Current High-Propylene Operating Setpoint | Maximum Permissible Limit |
|---|---|---|---|
| **Riser Outlet Temperature (ROT)** | 525°C – 532°C | **540°C – 544°C** | 550°C |
| **Combined Feed Preheat Temperature** | 210°C – 220°C | **225°C – 232°C** | 245°C |
| **Riser Top Operating Pressure** | 1.80 kg/cm²g | **1.95 – 2.05 kg/cm²g** | 2.30 kg/cm²g |
| **Regenerator Dense Bed Temperature** | 690°C – 705°C | **710°C – 718°C** | 735°C |
| **Disengager / Cyclone Temperature** | 520°C – 528°C | **536°C – 540°C** | 545°C |

**Temperature Impact on Propylene Selectivity:**
- Higher riser temperatures accelerate primary beta-scission and secondary cracking reactions.
- Raising the ROT from 525°C to 542°C increases propylene selectivity significantly from ~15.5 wt% to **19.8–20.5 wt%**.
- Temperatures exceeding 548°C cause excessive thermal non-selective cracking, exponentially multiplying dry gas yield (methane, ethane, ethylene), which overloads the Wet Gas Compressor (WGC) and degrades olefin recovery efficiency.

---

### 3. Run Rates & Propylene Selectivity Metrics

Under steady-state high-severity operations, current run rates and selectivity benchmarks for the MRPL PFCCU are established as follows:

- **Fresh Feed Processing Run Rate:** 255.0 to 275.0 t/h (Nominal: **260.0 t/h**, corresponding to ~2.2 MMTPA annualized throughput).
- **Propylene (C3=) Selectivity:** **19.8% to 20.8% by weight** on fresh feed basis.
- **Polymer-Grade Propylene Production Rate:** **42.0 to 51.5 t/h** (Telemetry Tag `PFCCU-C3-PROD`, standard continuous run rate: **42.0 t/h** PGP).
- **Gasoline (Naphtha) Yield:** 38.5 – 42.0 wt% (Research Octane Number RON: 94.5 – 96.0).
- **LPG Yield (Total C3/C4):** 28.5 – 31.5 wt%.
- **Light Cycle Oil (LCO):** 11.5 – 13.0 wt%.
- **Clarified Slurry Oil (CSO):** 4.0 – 5.5 wt%.
- **Coke Make:** 6.8 – 7.4 wt%.

---

### 4. Catalyst Circulation Dynamics & Cat-to-Oil (C/O) Ratio

Catalyst circulation rate is the critical operational lever controlling reactor heat balance, reaction severity, and residence time:

- **Regenerated Catalyst Circulation Rate:** **18.5 to 24.0 tons per minute** (regulated by double-disc regenerated catalyst slide valve `RCS-V-101`).
- **Catalyst-to-Oil (C/O) Ratio:** **14.0:1 to 16.8:1** (mass basis, compared to 5:1–7:1 in conventional fuels FCC).
- **Catalyst Inventory:** ~380 metric tons in unit circulation.
- **Zeolite Additive (ZSM-5):** Active equilibrium catalyst (ECAT) is formulated with **8.0 to 12.0 wt% proprietary pentasil ZSM-5 additive**.
- **Catalyst Activity (Microactivity Test MAT):** 68 – 72 vol% conversion.

**Role of ZSM-5 Zeolite Additive:**
The pore diameter of ZSM-5 (~5.4 Å × 5.6 Å) selectively admits straight-chain and monobranched gasoline-range olefins (C6–C9) while excluding bulky aromatic rings, selectively cracking them into propylene and isobutylene with minimal dry gas penalties.

---

### 5. Influence of Catalyst Circulation on Polymer-Grade Propylene Purity

Producing **Polymer-Grade Propylene (PGP)** requires strict downstream fractionation in the Propylene Recovery Unit (PRU) and C3 splitter column (`C-4401`). Catalyst circulation directly impacts product purity across four physical and chemical mechanisms:

#### A. Over-Cracking and C2 Slip (Ethylene / Ethane Carryover)
- Increasing catalyst circulation elevates the Cat/Oil ratio and catalyst contact time. 
- If circulation is pushed too high (>24 t/min) without corresponding feed rate increase, thermal cracking at the riser base escalates, generating excess **ethylene (C2=) and ethane (C2H6)**.
- In the downstream deethanizer column (`C-4303`), excess C2 cannot be completely stripped overhead, causing **C2 slip into the deethanizer bottoms**.
- This C2 slip contaminates the C3 splitter feed; ethylene concentrations >50 ppm wt cause the final propylene product to fail PGP purity specification (<30 ppm wt max C2 specification).

#### B. Trace Contaminants: MAPD (Methylacetylene and Propadiene)
- High catalyst circulation and elevated riser temperatures increase the dehydrogenation of propylene into **methylacetylene (MA, C3H4)** and **propadiene (PD, C3H4)**.
- Total MAPD concentration in cracked C3 feed can reach 1,800–3,500 ppm wt.
- MAPD is a severe poison to polypropylene Ziegler-Natta catalysts.
- To maintain polymer purity, the C3 stream must pass through a **Selective Hydrogenation Unit (SHU)** bed with palladium/alumina catalyst to hydrogenate MAPD down to **< 5 ppm wt** without over-hydrogenating propylene to propane.

#### C. Stripper Desorption & Delta Coke Balance
- Adequate catalyst residence time in the spent catalyst stripper (operating with 2.8–3.2 kg high-pressure steam per ton catalyst) is essential.
- Excessive circulation reduces spent catalyst residence time in the stripper, allowing entrained heavy hydrocarbons to enter the regenerator.
- This creates localized regenerator afterburning, damaging the hydrothermal stability of ZSM-5 zeolite, reducing active acid sites, and leading to erratic selectivity swings and increased byproduct impurities.

#### D. Catalyst Fines Carryover
- High velocity and circulation surges promote mechanical attrition of catalyst particles into fines (<20 microns).
- Fines carried into the main fractionator overhead can foul the wet gas compressor interstage coolers, trace caustic treaters, and amine absorbers, diminishing trace sulfur (COS, H2S) removal efficiency before the PRU.

---

### 6. Polymer-Grade Propylene (PGP) Statutory Product Specifications

The final product from MRPL Unit 440 must meet the stringent requirements of ASTM D5234 and internal MRPL petrochemical standards:

| Component / Contaminant | Polymer-Grade Propylene (PGP) Limit | Test Method | Impact on Downstream Polypropylene |
|---|---|---|---|
| **Propylene (C3H6) Purity** | **≥ 99.50 wt% min** (Typical: 99.75 wt%) | Gas Chromatography (GC) | Polymer yield, tacticity, and resin melt flow index |
| **Propane (C3H8)** | **≤ 0.50 wt% max** | GC | Inert diluent; lowers polymerization reactor throughput |
| **Ethylene (C2H4)** | **≤ 30 ppm wt max** | GC | Uncontrolled copolymerization; alters polymer crystallinity |
| **Ethane (C2H6)** | **≤ 50 ppm wt max** | GC | Inert; reduces C3 splitter efficiency |
| **MAPD (MA + PD)** | **≤ 5 ppm wt max** | GC | Active catalyst site termination; polymer chain breakage |
| **Carbon Monoxide (CO)** | **≤ 2.0 ppm vol max** | Methanation GC / IR | Severe Ziegler-Natta active center catalyst poison |
| **Carbon Dioxide (CO2)** | **≤ 5.0 ppm vol max** | GC / Methanizer | Catalyst deactivation and co-catalyst complexing |
| **Total Sulfur (including COS)**| **≤ 1.0 ppm wt max** | UV Fluorescence / GC-SCD | Catalyst poisoning; odor in final polypropylene resins |
| **Water (H2O)** | **≤ 5.0 ppm wt max** | Capacitance Hygrometer | Destroys triethylaluminum (TEAL) catalyst co-promoter |
| **Oxygen (O2)** | **≤ 2.0 ppm vol max** | Electrochemical | Rapid polymerization catalyst deactivation |

---

### 7. Operating Envelope Summary for Plant Operators

1. **Riser Outlet Temperature:** Maintain coil ROT strictly within **540°C – 544°C** for optimal 19.8–20.5 wt% propylene yield without overloading the wet gas compressor.
2. **Catalyst Circulation Rate:** Modulate regenerated slide valve `RCS-V-101` to maintain **19.0 – 22.0 t/min** (Cat/Oil ratio 15.0:1 – 16.5:1).
3. **Deethanizer Reboiler Duty:** Control deethanizer column bottoms temperature to ensure **ethylene slip into C3 splitter is < 25 ppm wt**.
4. **SHU Hydrogen Ratio:** Maintain H2/MAPD molar ratio at **1.15 : 1.0** across the selective hydrogenation reactor to guarantee **MAPD < 5 ppm wt** at the PRU outlet.
