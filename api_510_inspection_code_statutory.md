# Statutory Standard: API 510 & API RP 939-C Engineering Reference

## 1. Scope & Jurisdiction
This document extracts mandatory requirements governing pressure vessels in petroleum refineries under **API 510: Pressure Vessel Inspection Code (Maintenance Inspection, Rating, Repair, and Alteration)** and **API RP 939-C: Guidelines for Avoiding Sulfidation (Sulfidic) Corrosion Failures in Oil Refineries**.

## 2. API 510 Section 7: Minimum Thickness Evaluation
Under Section 7.1.1, the minimum required thickness for a pressure vessel shell subjected to internal design pressure is determined in accordance with the ASME Boiler and Pressure Vessel Code (Section VIII, Division 1, Paragraph UG-27):

$$t_{min} = \frac{P \cdot R}{S \cdot E - 0.6 \cdot P}$$

Where:
- $P$ = Maximum allowable working pressure (MAWP) or design pressure in gauge units (psi or bar).
- $R$ = Inside radius of the shell course under evaluation (inches or mm).
- $S$ = Maximum allowable stress value for the specified material of construction at design metal temperature (from ASME Section II, Part D). For SA-516 Grade 70 at 380°C, allowable stress $S = 120.7 \text{ MPa} (17,500 \text{ psi})$.
- $E$ = Weld joint efficiency factor (1.00 for full volumetric RT per UW-11(a); 0.85 for spot RT per UW-52).

### Retirement Thickness Criterion:
If the actual thickness measured during ultrasonic examination ($t_{act}$) minus corrosion allowance is less than the calculated $t_{min}$, the vessel course violates statutory safety thresholds. The owner-user must immediately execute one of three mandatory engineering actions:
1. Derate the vessel MAWP down to the maximum safe pressure allowable under $t_{act}$.
2. Perform an ASME Sec VIII / API 510 weld overlay repair or relining using a corrosion-resistant alloy (e.g. Inconel 625 or 9-Cr alloy).
3. Retire and isolate the equipment course from hazardous process containment.

## 3. API RP 939-C: Sulfidation (Sulfidic) Corrosion in Crude Units
Sulfidation corrosion is the progressive thinning of iron-based alloys resulting from chemical reaction with reactive sulfur species ($H_2S$, mercaptans, and polysulfides) present in crude oil feedstocks at temperatures exceeding 230°C (450°F).

Key Mechanisms:
- **Corrosion Rate Acceleration:** In carbon steel piping and column shells, sulfidation rates accelerate non-linearly above 260°C, often reaching 0.5 mm/year to 1.5 mm/year when processing Middle Eastern sour crudes (such as Arabian Heavy or Basrah Medium with sulfur > 2.5 wt%).
- **Silicon Influence:** Carbon steels with low silicon content (< 0.10 wt% Si) corrode at up to 2 to 3 times the rate of standard killed carbon steels.
- **Recommended Remediation:** Upgrade metallurgy to 5Cr-0.5Mo, 9Cr-1Mo, or in-situ weld overlay cladding with Nickel-Chromium alloy 625 (UNS N06625).
