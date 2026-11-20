"""Single source of truth for the model inputs.

Both the training scripts (ml/) and the web application (risk/) import this file,
so the order and meaning of the features can never drift apart.
These are the *candidate* variables listed in the project proposal (section 3.9).
The final list must be confirmed against the MRRH records after the feasibility review.
"""

SYMPTOMS = [
    ("headache", "Headache"),
    ("blurred_vision", "Blurred vision"),
    ("vaginal_bleeding", "Vaginal bleeding"),
    ("abdominal_pain", "Abdominal pain"),
    ("fever", "Fever"),
    ("swelling", "Swelling (face, hands or feet)"),
    ("breathing_difficulty", "Difficulty breathing"),
]
NUMERIC = [
    "age",
    "gestational_weeks",
    "systolic_bp",
    "diastolic_bp",
    "glucose_mmol",
    "temp_c",
    "heart_rate",
    "parity",
]
HISTORY = ["previous_caesarean", "pre_existing_condition"]

SYMPTOM_KEYS = [k for k, _ in SYMPTOMS]
FEATURE_ORDER = NUMERIC + SYMPTOM_KEYS + HISTORY
CLASSES = ["low", "medium", "high"]

# Plausibility limits used for input validation (data-entry sanity checks, not clinical thresholds).
RANGES = {
    "age": (10, 60),
    "gestational_weeks": (1, 45),
    "systolic_bp": (60, 260),
    "diastolic_bp": (30, 160),
    "glucose_mmol": (1.0, 40.0),
    "temp_c": (33.0, 43.0),
    "heart_rate": (30, 220),
    "parity": (0, 20),
}
