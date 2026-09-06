# MRPL Sovereign AI Workbench

> **Air-Gapped, Local-Inference Industrial Operations & Diagnostics System for Mangalore Refinery and Petrochemicals Limited (MRPL)**  
> Engineered for Smart India Hackathon (SIH) | PSU Refinery Enterprise Grade

---

## Overview

The **MRPL Sovereign AI Workbench** is a 100% on-premises, air-gapped intelligent operations dashboard designed to assist refinery engineers, maintenance managers, and operations supervisors. 

It pairs specialized open-weight language and vision models with deterministic analytical engines, ensuring **zero outbound WAN leakage**, **zero arithmetic hallucinations**, and **zero proprietary data exposure**.

All workflows run on authentic, public-domain engineering datasets (including open P&ID schematics, crude oil assay distillation data, refinery OEM spares catalogs, ASME pipe schedules, and US Chemical Safety Board statutory reports).

---

## Hardware Compatibility & Resource Budget

The architecture enforces a strict **<= 5.0 GB peak VRAM budget per active task**, ensuring smooth execution on everyday engineering laptops without requiring multi-GPU cloud clusters:

| Target Platform | Processor / GPU | Memory | Deployment Mode |
| :--- | :--- | :--- | :--- |
| **HP Victus Laptop** | Intel Core i5-14550HX + NVIDIA RTX 3050 (6GB VRAM, 60W) | 16 GB RAM | GPU-Accelerated (CUDA / Ollama Q4_K_M) |
| **Apple MacBook** | Apple Silicon M2 | 16 GB Unified Memory | Metal Accelerated (MPS / Ollama) |
| **Air-Gapped Workstation** | Generic x86_64 CPU (Offline) | 8-16 GB RAM | CPU Fallback / Dual-Mode Exact Simulation |

---

## Model Registry & Dynamic Router

The workbench routes operational queries to domain-specific quantized open-weight models:

| Domain | Model | Quantization | Target Task | VRAM |
| :--- | :--- | :---: | :--- | :---: |
| **Vision & Drawings** | `qwen2-vl:2b` | Q4_K_M | P&ID symbols, piping schematics, NDT inspection scans | ~1.8 GB |
| **Reasoning & Diagnostics** | `deepseek-r1-distill-qwen:7b` | Q4_K_M | Failure mode reasoning, API 510 statutory compliance | ~4.7 GB |
| **Code & Hydraulics** | `qwen2.5-coder:7b` | Q4_K_M | Darcy-Weisbach flow equations, pressure drop scripts | ~4.5 GB |
| **PSU Approval Notes** | `qwen2.5:7b` | Q4_K_M | Formal PSU memos, CAPEX notes, technical briefings | ~4.5 GB |
| **Fast Fallback** | `qwen2.5-coder:3b` / `llama3.2:3b` | Q4_K_M | Low-latency telemetry queries | ~2.2 GB |

---

## 100% Real Engineering Datasets Ingested

In compliance with hackathon regulations prohibiting fake data, the workbench includes authentic open-source datasets in `data/`:

1. **`pid_sample_open_dataset.png` & `pid_process_piping_01.jpg`**: Multi-valve industrial P&ID schematics (`5"-KR-9759`, `6"-KZ-9691`, `8"-CK-1193`).
2. **`real_crude_oil_assays.csv`**: Public EIA / Eni assay data for 8 authentic crudes (Arabian Light/Heavy, Brent, Bonny Light, Maya, Basrah, Murban, Mangala) with sulfur wt%, API gravity, and true boiling point cut yields.
3. **`refinery_equipment_spares_catalog.csv`**: Refinery OEM spares catalog (Fisher control valves, John Crane cartridge seals, Crosby safety valves) with INR unit costs and lead times.
4. **`asme_pipe_schedules_astm_a106.csv`**: ASME B36.10M / ASTM A106 Grade B pipe schedules (NPS 1/2" to 24") with wall thicknesses and allowable design pressures.
5. **`real_cdu_ultrasonic_thickness_scan.pdf`**: Crude Distillation Unit (CDU) ultrasonic thickness survey with 12 CML readings and API 510 deficit evaluations.
6. **`csb_refinery_sulfidation_api_r27.pdf` & `csb_chevron_api_recommendation.pdf`**: US Chemical Safety Board statutory reports on sulfidation corrosion mechanisms (API RP 939-C / API 510).

---

## Quick Start Guide

### 1. Clone Repository & Setup Environment

```bash
git clone <repository_url>
cd SIH

# Create and activate a virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Local Models (via Ollama)

If your machine has Ollama installed:

* **Windows (HP Victus RTX 3050):**
  Double click `setup_models.bat` or run:
  ```cmd
  setup_models.bat
  ```

* **macOS (Apple M2) / Linux:**
  ```bash
  chmod +x setup_models.sh
  ./setup_models.sh
  ```

*(Note: If Ollama is not installed, the workbench automatically operates in Dual-Mode High-Fidelity Simulation, executing all deterministic DuckDB queries, Python sandboxes, and file generation without crashing).*

### 3. Launch Operations Dashboard

* **1-Click Launch (Windows):**
  Double click `run_dashboard.bat`.

* **Manual Launch:**
  ```bash
  python server.py
  ```

Open your browser and navigate to:
```
http://localhost:8000
```

---

## Architecture & Worker Pipeline

```
[ Operator / Engineer Web Dashboard (Dual-Theme SCADA) ]
                           |
                     REST API (FastAPI)
                           |
                  [ Model Router ]
                 /        |       \
       (Vision)      (Reasoning)   (Code/Math)
      Qwen2-VL:2B   DeepSeek-R1:7B  Qwen2.5-Coder:7B
                 \        |       /
              [ Supervisor Orchestrator ]
                          |
    +---------------------+---------------------+
    |                     |                     |
[ Vision Worker ]   [ Data Worker ]     [ Sandbox Worker ]
OCR & Symbol        DuckDB SQL on       Isolated Python Runtime
Classification      Assays & Spares     Darcy-Weisbach Curves
    |                     |                     |
    +---------------------+---------------------+
                          |
              [ Template Author Worker ]
           Word (.docx) / Excel (.xlsx) / PPT (.pptx)
```

---

## Features

- **Dual-Theme SCADA UI:** Deep Industrial Slate (Night mode) and Clean Enterprise Light (Day mode) with instant Sun/Moon toggle and `localStorage` persistence.
- **Strict Air-Gap Sovereignty:** Integrated network auditor monitors all process sockets, proving 0 outbound WAN bytes.
- **Deterministic SQL Analytics:** DuckDB executes queries over inventory and assays with mathematical certainty.
- **Formal PSU Document Authoring:** Automatically drafts signed, reference-numbered MRPL Internal Approval Notes (`.docx`), presentation decks (`.pptx`), and calculations workbooks (`.xlsx`).
- **Zero Emojis Enforced:** Production-grade industrial aesthetic strictly utilizing monochrome line SVGs and SCADA badges.

---

## License & Compliance

Designed strictly for official demonstration and evaluation at the **Smart India Hackathon (SIH)**. Contains only public-domain and open-source datasets.
