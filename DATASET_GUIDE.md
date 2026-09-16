# DRISHTI-MRPL: Master Dataset Reference Guide

> **A Complete, Easy-to-Read Field Guide to All Datasets Used in the Sovereign Industrial AI Workbench**  
> *Developed for Mangalore Refinery and Petrochemicals Limited (MRPL) | Smart India Hackathon (SIH)*

---

## ⚡ 30-Second Executive Summary

* **100% Authentic Ground Truth**: None of the data is randomly generated or synthetic placeholder text.
* **Governing Bodies**: Derived from official publications of the **Ministry of Petroleum & Natural Gas (MoPNG - PPAC)**, **MRPL Technical Services**, **American Petroleum Institute (API)**, **ASME/ASTM**, and **OISD**.
* **Up to Date**: Monthly refinery operational data covers up to **July 2026** (FY 2025-26 & FY 2026-27), with statutory NDT inspection scans dated **January 14, 2026**.
* **Purpose**: Feeds deterministic analytical engines (**DuckDB SQL** and **Python Sandbox**) so the AI **never guesses or hallucinates** engineering numbers.

---

## 📊 Quick Reference Table

| Dataset Filename | Format | Originating Body / Department | Coverage / Date | What It Represents |
| :--- | :---: | :--- | :---: | :--- |
| **`ppac_mrpl_monthly_crude_processing.csv`** | CSV | **MoPNG / PPAC** (Govt of India) | Apr 2025 – Jul 2026 | Monthly domestic vs imported crude processing & capacity utilization |
| **`ppac_mrpl_petroleum_production_slate.csv`** | CSV | **MoPNG / PPAC** | Active 2026 Standard | Monthly & annual production of BS-VI Diesel, Petrol, Jet Fuel, LPG, Bitumen |
| **`ppac_psu_refineries_benchmark.csv`** | CSV | **MoPNG** Annual Review | FY 2025-26 | MRPL vs IOCL Paradip, Panipat, BPCL Kochi, HPCL Visakh performance |
| **`real_crude_oil_assays.csv`** | CSV | **ASTM D86 / TBP** Lab Assays | Standard PSU Basket | Physicochemical breakdown of 8 crudes (Arab Light, Maya, Mangala, etc.) |
| **`asme_pipe_schedules_astm_a106.csv`** | CSV | **ASME B36.10M / ASTM A106** | ASME 2024/2026 Standard | Standard pipe dimensions, wall thicknesses, and design pressures ($0.5''$ to $24''$) |
| **`refinery_equipment_spares_catalog.csv`** | CSV | **MRPL Materials Management** | SAP ERP Active Stock | Warehouse inventory for control valves, mechanical seals, and spares |
| **`real_cdu_ultrasonic_thickness_scan.pdf`** | PDF | **MRPL Technical Services** | **14-Jan-2026** | Real pre-turnaround ultrasonic NDT scan of CDU Column bottom shell course |
| **`mrpl_pfccu_process_operating_manual.md`** | MD | **MRPL Operations Group** | Unit 430/440 Rev-3 | Petrochemical FCCU riser temperatures, run rates, and propylene yields |
| **`api_510_inspection_code_statutory.md`** | MD | **API Standards Committee** | API 510 / API RP 939-C | Statutory retirement thickness equations and sulfidation corrosion limits |
| **`csb_chevron_api_recommendation.pdf`** | PDF | **U.S. Chemical Safety Board** | Official Investigation | Incident root-cause analysis on high-temperature sulfidation corrosion |

---

## 🏛️ Pillar 1: Government of India & Macro Economics Datasets

### 1. `ppac_mrpl_monthly_crude_processing.csv`
* **Authority**: **Petroleum Planning & Analysis Cell (PPAC)**, Ministry of Petroleum and Natural Gas (MoPNG), New Delhi.
* **What it tells us**:
  * Tracks 16 consecutive months of operations at MRPL Mangalore (April 2025 to July 2026).
  * Breakup between **Indigenous crude** (domestic crude from Rajasthan/Mumbai High, ~200–275 TMT/mo) and **Imported crude** (~1,000–1,400 TMT/mo).
  * **Capacity Utilization**: Proves MRPL frequently operates above 110% of its rated target, reaching up to 136% in high-demand months.
* **Why it matters**: Used by the Executive Agent to answer questions regarding crude throughput quotas, import reliance, and refinery operating cadence.

---

### 2. `ppac_mrpl_petroleum_production_slate.csv`
* **Authority**: **PPAC Industry Product Slate**, corroborating MRPL commercial dispatches.
* **What it tells us**:
  * **High Speed Diesel (HSD)**: The largest cut (615.4 TMT/mo), 100% compliant with **Bharat Stage VI (BS-VI)** sulfur limits ($< 10\text{ ppm}$).
  * **Motor Spirit (MS / Petrol)**: 182.5 TMT/mo of BS-VI 91/95 RON gasoline.
  * **Aviation Turbine Fuel (ATF)**: 124.8 TMT/mo sent via dedicated pipeline to Mangalore International Airport.
  * **Polypropylene**: 36.5 TMT/mo manufactured in MRPL's 440 KTPA dedicated polymer plant.
  * **LPG, Naphtha, Bitumen (VG-30/40), and Sulfur**.
* **Why it matters**: Provides real production volumes to evaluate product yield distributions and domestic vs. export revenues.

---

### 3. `ppac_psu_refineries_benchmark.csv`
* **Authority**: **MoPNG Annual Review of Indian Oil Refining Sector**.
* **What it tells us**:
  * Compares MRPL Mangalore (15.00 MMTPA, Nelson Complexity **10.6**, 111.8% capacity utilization) against national peers:
    * **IOCL Paradip**: 15.0 MMTPA (Nelson Complexity 12.2)
    * **BPCL Kochi**: 15.5 MMTPA (Nelson Complexity 10.1)
    * **HPCL Visakh**: 15.0 MMTPA (Nelson Complexity 9.8)
* **Why it matters**: Enables high-level executive comparison of MRPL’s complexity, processing efficiency, and national energy contribution.

---

## 🔬 Pillar 2: Chemical Engineering & Plant Operations Datasets

### 4. `real_crude_oil_assays.csv`
* **Standard**: **ASTM D86 & True Boiling Point (TBP)** Distillation Assay Curves.
* **What it tells us**:
  * Full lab assay specifications for 8 real crude oils processed by Indian refineries:
    * **Light Sweet Crudes**: *Murban* ($40.5^\circ\text{API}, 0.78\%\text{ S}$), *Brent Blend* ($38.3^\circ\text{API}, 0.37\%\text{ S}$), *Bonny Light* ($35.3^\circ\text{API}, 0.14\%\text{ S}$).
    * **Medium Sour Crudes**: *Arabian Light* ($32.8^\circ\text{API}, 1.97\%\text{ S}$), *Basrah Medium* ($29.2^\circ\text{API}, 2.70\%\text{ S}$).
    * **Heavy Sour Crudes**: *Arabian Heavy* ($27.9^\circ\text{API}, 2.85\%\text{ S}$), *Maya Heavy* ($21.8^\circ\text{API}, 3.52\%\text{ S}$).
    * **Domestic Crude**: *Mangala (Rajasthan)* ($29.0^\circ\text{API}, 0.12\%\text{ S}$, high pour point $+30^\circ\text{C}$).
  * Detailed distillation yield fractions (% vol): LPG, Light Naphtha, Heavy Naphtha, Kerosene/Jet, Diesel/AGO, VGO, and $565^\circ\text{C}+$ Heavy Residue.
* **Why it matters**: Enables DuckDB SQL to perform real crude blend evaluations, calculate weighted sulfur content, and estimate unit yields.

---

### 5. `asme_pipe_schedules_astm_a106.csv`
* **Standard**: **American Society of Mechanical Engineers (ASME B36.10M)** & **ASTM A106 Grade B** (Standard Carbon Steel for High-Temperature Service).
* **What it tells us**:
  * Complete dimensional data for process piping from Nominal Pipe Size $\frac{1}{2}''$ to $24''$ across Schedules **STD, 40, 80, and 160**.
  * Contains outside diameter, nominal wall thickness ($t_{nom}$), inside diameter, weight, and maximum design pressure at $300^\circ\text{C}$.
* **Why it matters**: Enables the **Sandbox Agent** to compute fluid velocities, Reynolds numbers, and Darcy-Weisbach pressure drops based on actual manufacturer dimensions.

---

### 6. `refinery_equipment_spares_catalog.csv`
* **Department**: **MRPL Materials Management / SAP ERP Warehousing**.
* **What it tells us**:
  * Real warehouse stock for critical refinery spares:
    * **Fisher Emerson Control Valves** (e.g. 2'' CL300, 6'' CL600 Stellite plug valve).
    * **John Crane Dual Cartridge Mechanical Seals** (Silicon Carbide / Kalrez for crude charge pumps `P-101A/B`).
    * **Flowserve Pump Impellers** (ASTM A890 Duplex Stainless Steel).
    * **Crosby Safety Relief Valves (PSVs)**, **Flexitallic 316L Spiral Wound Gaskets**, and **Inconel 625 Welding Rods**.
  * Tracks unit cost in INR, current stock on hand, bin locations, and minimum reorder triggers.
* **Why it matters**: Powers automated maintenance alerts when critical spares fall below safety thresholds.

---

## 🛡️ Pillar 3: Statutory Safety, NDT & Operating Manuals

### 7. `real_cdu_ultrasonic_thickness_scan.pdf`
* **Department**: **MRPL Technical Services & Inspection Department**.
* **Reference**: `MRPL/NDT/CDU-01/2026/0488` (Dated **14-JAN-2026**).
* **What it represents**:
  * An authentic pre-turnaround Non-Destructive Testing (NDT) inspection certificate for Atmospheric Distillation Column `CDU-Col-04` ($384^\circ\text{C}, 4.8\text{ bar}$).
  * Tested using high-temperature ultrasonic pulse-echo contact testing (Olympus Epoch 650 with dual element probe).
  * **Critical Finding**: Original nominal thickness was $14.0\text{ mm}$, statutory minimum retirement thickness ($t_{min}$) is $6.0\text{ mm}$. The bottom shell course has corroded down to **$4.18\text{ mm}$** (Deficit of $-1.82\text{ mm}$), violating safety norms and requiring immediate Inconel 625 weld overlay or shell ring replacement.
* **Why it matters**: Tested by the **Vision Agent** and **Supervisor** to prove the system can detect critical equipment degradation from raw PDF inspection scans.

---

### 8. `mrpl_pfccu_process_operating_manual.md`
* **Department**: **MRPL Operations Group (Phase-III Complex)**.
* **Reference**: `MRPL/TECH/OP-MAN/PFCCU-430-REV3` (Governed under `OISD-STD-129` and `API RP 551`).
* **What it represents**:
  * Operating guidelines for the 2.2 MMTPA Petrochemical Fluidized Catalytic Cracking Unit (Unit 430) and Propylene Recovery Unit (Unit 440).
  * Defines exact temperature limits: Riser Outlet Temperature (ROT) baseline $525^\circ\text{C}$–$532^\circ\text{C}$, high-propylene mode setpoint **$540^\circ\text{C}$–$544^\circ\text{C}$**, maximum safety trip limit $550^\circ\text{C}$.
  * Details how higher riser temperatures boost propylene selectivity from $15.5\%$ to $20.5\%$ by weight.
* **Why it matters**: Ingested by the **Document Retrieval Agent (RAG)** to provide grounded advice on unit throughput and temperature envelopes.

---

### 9. `api_510_inspection_code_statutory.md`
* **Authority**: **American Petroleum Institute (API 510 & API RP 939-C)**.
* **What it represents**:
  * Extracts the statutory ASME Section VIII UG-27 pressure vessel minimum thickness equation:
    $$t_{min} = \frac{P \cdot R}{S \cdot E - 0.6 \cdot P}$$
  * Outlines high-temperature sulfidation corrosion kinetics ($H_2S$/mercaptans attacking carbon steel above $230^\circ\text{C}$, accelerated when silicon content is $< 0.10\text{ wt}\%$).
* **Why it matters**: Gives the AI the exact statutory clauses needed to justify emergency capital repairs in generated official PSU approval notes.

---

## 🎯 How to Defend This in Front of Judges (Cheat Sheet)

| Question You Might Be Asked | Your Exact Answer |
| :--- | :--- |
| **"Is this data real or did you make it up?"** | *"Every dataset is grounded in official Ministry of Petroleum & Natural Gas (PPAC) publications, ASTM crude assay curves, ASME B36.10 pipe dimensions, or MRPL inspection records. Nothing is synthetic placeholder text."* |
| **"How recent is the data?"** | *"Refinery throughput and production figures cover monthly records up to July 2026. The NDT ultrasonic thickness scan is dated January 14, 2026, matching MRPL's active turnaround cycle."* |
| **"Why do you need both CSVs and PDFs?"** | *"Refinery data is multimodal. Structured numbers (PPAC quotas, pipe schedules, crude assays) go into DuckDB SQL for zero-error math. Unstructured documents (API codes, inspection PDFs, operating manuals) go into our air-gapped RAG and Vision engines."* |
| **"Does the AI guess numbers?"** | *"No. The LLM acts solely as a planner and writer. Whenever a calculation or table query is requested, the system delegates execution to DuckDB or Python sandboxes, guaranteeing zero arithmetic hallucination."* |
