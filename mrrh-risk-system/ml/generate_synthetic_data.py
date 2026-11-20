"""Generate a SYNTHETIC demonstration dataset.

IMPORTANT
---------
* These are invented records. They are NOT MRRH data and describe no real woman.
* The risk label is made with simple PLACEHOLDER scoring rules plus random noise, only so
  the training pipeline and the web system can be demonstrated end to end.
* The rules are NOT clinical guidance. The proposal (section 3.9) requires a locally
  approved, non-circular label from MRRH obstetric specialists before any model can be
  called locally valid. Replace this file and the label with real, approved data then.
"""
import csv
import random
from pathlib import Path

SEED = 20260610
N_PATIENTS = 3200
OUT = Path(__file__).resolve().parent / "data" / "synthetic_records.csv"


def clip(x, lo, hi):
    return max(lo, min(hi, x))


def score(r):
    s = 0
    if r["systolic_bp"] >= 160 or r["diastolic_bp"] >= 110:
        s += 3
    elif r["systolic_bp"] >= 140 or r["diastolic_bp"] >= 90:
        s += 2
    if r["glucose_mmol"] >= 11.1:
        s += 3
    elif r["glucose_mmol"] >= 7.8:
        s += 2
    if r["temp_c"] >= 38.0:
        s += 2
    elif r["temp_c"] >= 37.5:
        s += 1
    if r["heart_rate"] >= 120 or r["heart_rate"] < 50:
        s += 2
    elif r["heart_rate"] >= 100:
        s += 1
    if r["age"] < 18 or r["age"] >= 35:
        s += 1
    if r["age"] >= 40:
        s += 1
    s += 3 * r["vaginal_bleeding"] + 2 * r["blurred_vision"] + 2 * r["breathing_difficulty"]
    s += r["headache"] + r["abdominal_pain"] + r["swelling"] + r["fever"]
    s += r["previous_caesarean"] + 2 * r["pre_existing_condition"]
    if r["parity"] >= 5:
        s += 1
    return s


def label(s, rng):
    cls = 0 if s <= 2 else (1 if s <= 5 else 2)
    if rng.random() < 0.08:  # label noise, to mimic inconsistent real-world labelling
        cls = clip(cls + rng.choice([-1, 1]), 0, 2)
    return ["low", "medium", "high"][cls]


def main():
    rng = random.Random(SEED)
    rows = []
    for pid in range(1, N_PATIENTS + 1):
        first_year = rng.choices([2021, 2022, 2023, 2024, 2025], weights=[18, 19, 20, 21, 22])[0]
        age = int(clip(rng.gauss(27, 6.5), 14, 46))
        parity = int(clip(round(rng.gauss(2, 1.8)), 0, 9))
        prev_cs = int(rng.random() < 0.14 and parity > 0)
        pre_exist = int(rng.random() < 0.09)
        for enc in range(rng.choices([1, 2, 3], weights=[60, 28, 12])[0]):
            year = min(2025, first_year + (1 if enc and rng.random() < 0.3 else 0))
            hyper = rng.random() < 0.16
            r = {
                "patient_id": f"P{pid:05d}",
                "visit_year": year,
                "age": age,
                "gestational_weeks": int(clip(rng.gauss(31, 7), 6, 42)),
                "systolic_bp": int(clip(rng.gauss(138 if hyper else 112, 14 if hyper else 11), 80, 210)),
                "diastolic_bp": 0,
                "glucose_mmol": round(clip(rng.lognormvariate(1.75, 0.28), 3.0, 22.0), 1),
                "temp_c": round(clip(rng.gauss(36.8, 0.55), 35.0, 40.5), 1),
                "heart_rate": int(clip(rng.gauss(86, 13), 48, 150)),
                "parity": parity,
                "headache": int(rng.random() < (0.35 if hyper else 0.12)),
                "blurred_vision": int(rng.random() < (0.18 if hyper else 0.03)),
                "vaginal_bleeding": int(rng.random() < 0.05),
                "abdominal_pain": int(rng.random() < 0.12),
                "fever": 0,
                "swelling": int(rng.random() < (0.35 if hyper else 0.10)),
                "breathing_difficulty": int(rng.random() < 0.04),
                "previous_caesarean": prev_cs,
                "pre_existing_condition": pre_exist,
            }
            r["diastolic_bp"] = int(clip(r["systolic_bp"] * 0.62 + rng.gauss(4, 6), 45, 130))
            r["fever"] = int(r["temp_c"] >= 37.8 and rng.random() < 0.8)
            r["risk_label"] = label(score(r), rng)
            rows.append(r)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(f"wrote {len(rows)} synthetic encounters for {N_PATIENTS} synthetic patients -> {OUT}")
    print(Counter(r["risk_label"] for r in rows))


if __name__ == "__main__":
    main()
