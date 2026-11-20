# Model card (demonstration model)

**Status:** demonstration only. Not clinically valid. Not for patient care.

| | |
|---|---|
| Task | Three-class classification: low, medium or high maternal risk category |
| Inputs (17) | Age, gestational weeks, systolic and diastolic blood pressure, blood glucose (mmol/L), temperature, heart rate, parity; 7 symptom flags; previous caesarean; pre-existing condition |
| Candidates | Multinomial logistic regression, random forest, support vector machine |
| Deployed | The best exportable candidate by validation macro-F1 (see About page / `risk/artifacts/metrics.json`) |
| Data | 4,890 **synthetic** encounters for 3,200 **synthetic** patients. Not MRRH data |
| Label | Placeholder scoring rules plus 8% label noise. Not clinical guidance, and circular by design, because the model learns the rule |
| Partitioning | Patient-level and temporal: first seen 2021-2023 train, 2024 validation, 2025 test |
| Metrics reported | Macro-F1, per-class precision/recall/F1, balanced accuracy, confusion matrix, one-vs-rest ROC-AUC, multiclass Brier score, patient-level bootstrap 95% interval |
| Probabilities | Stored for audit, not shown to users (calibration not yet assessed on real data) |

## What the numbers mean
They describe how well a model recovers an invented rule from noisy invented data. They say nothing about performance at MRRH. In the current run the selected model finds roughly 4 in 10 high-risk cases in the synthetic test set, which illustrates why high-risk recall must be reported and why a model needs local validation before any use.

## Before real use (from the proposal)
1. Ethics clearance and written MRRH authorisation.
2. Feasibility review of MRRH records: variables, labels, class counts, missing data.
3. A clinically approved, non-circular risk label agreed with obstetric specialists.
4. Retrain on approved, de-identified records with the same patient-level partitioning, and evaluate on later local records.
5. MRRH obstetric staff approve any alert or referral wording.
6. Formative usability testing with healthcare workers.
