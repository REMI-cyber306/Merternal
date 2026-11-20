# MRRH Maternal Risk Decision-Support Prototype

Software part of the project **Machine Learning-Based Maternal Health Risk Prediction: A Case Study of Mbarara Regional Referral Hospital** (Ashaba Augustus, 2024/BSIT/009/F, University of Saint Joseph Mbarara).

A Django web application that takes recorded maternal and clinical values and shows a **low / medium / high** risk category for clinical review. It follows the proposal: Django, PostgreSQL, Python machine learning, role-based access, coded study IDs, no diagnosis or referral decisions, and class probabilities hidden until calibration is assessed.

> **Read this first.** There is no MRRH data in this project. The model is trained on **synthetic demonstration data** with **placeholder labelling rules**. It shows that the pipeline and the web system work end to end. It is **not clinically valid and must not be used for patient care**. The proposal (section 3.9) requires a locally approved, non-circular risk label and ethics clearance before real data are used. The yellow banner on every page stays on (`DEMO_MODE=1`) until then.

## What is inside

```
mrrh-risk-system/
├── api/index.py            Vercel entry point (exposes the Django WSGI app)
├── vercel.json             Routes every request to the Django function
├── requirements.txt        Runtime packages (Django, WhiteNoise, PostgreSQL driver, NumPy)
├── requirements-train.txt  Extra packages for retraining (scikit-learn, pandas...) - not deployed
├── config/                 Django settings, urls, wsgi
├── risk/                   The application
│   ├── features.py         The model inputs (single source of truth, from proposal 3.9)
│   ├── models.py           Assessment record (coded data only)
│   ├── forms.py            Validated entry form (ranges, BP check, study-code format)
│   ├── predictor.py        Runs the exported model with NumPy only
│   ├── views.py, urls.py   Dashboard, assessment, result, history, CSV export, About, /healthz
│   ├── templates/, static/ Bootstrap interface (self-hosted, no CDN)
│   ├── artifacts/          model.npz, model_meta.json, metrics.json (output of ml/train.py)
│   ├── management/commands/setup_demo.py   Creates groups and demo users
│   └── tests.py            20 automated tests
├── ml/
│   ├── generate_synthetic_data.py   Invented records + placeholder label rules
│   ├── train.py                     Patient-level temporal split, 3 models, metrics, export
│   └── data/                        Generated CSV (git-ignored)
├── staticfiles/            Pre-collected static files (committed so Vercel can serve them)
└── docs/                   DEPLOY_VERCEL.md, MODEL_CARD.md
```

## Run it on your computer

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # Windows: copy .env.example .env
python manage.py migrate
DEMO_PASSWORD='choose-a-long-password' python manage.py setup_demo --users   # Windows: set DEMO_PASSWORD=... first
python manage.py runserver
```

Open http://127.0.0.1:8000 and log in as `clinician` (healthcare worker) or `supervisor` (sees all assessments and can export CSV). Create an administrator with `python manage.py createsuperuser`.

Run the tests: `python manage.py test risk`

## Roles

| Role | Can do |
|---|---|
| Healthcare worker | Enter assessments, see only their own results and history |
| Supervisor (`is_staff`) | See all assessments, export CSV |
| Administrator (superuser) | Manage users in `/admin/`. Assessments are read-only there, to keep the audit trail intact |

## Retrain the model

```bash
pip install -r requirements-train.txt
python ml/generate_synthetic_data.py
python ml/train.py
```

`train.py` compares multinomial logistic regression, random forest and a support vector machine with patient-grouped cross-validation, selects on **validation** macro-F1, evaluates the **test** set once, reports class-specific metrics, calibration-related Brier score and a patient-level bootstrap interval, then exports the model to `risk/artifacts/`. It also checks that the NumPy runtime reproduces scikit-learn's probabilities. The exported model must be committed for deployment.

When real, approved MRRH data exist: replace the CSV (same columns), keep the patient-level partitioning, and update `risk/features.py` to the variables actually available.

## Deploy to Vercel

See `docs/DEPLOY_VERCEL.md` for the full step-by-step guide.

## How it maps to the proposal

| Proposal | Where |
|---|---|
| 3.9 variables and outcome | `risk/features.py`, `ml/generate_synthetic_data.py` |
| 3.11-3.12 ML cycle, patient-level temporal split | `ml/train.py` |
| 3.13-3.14 three models, class-specific metrics, bootstrap | `ml/train.py`, About page |
| 3.15 web system (Django, PostgreSQL, Bootstrap), safeguards | `risk/`, `config/` |
| 3.16 technical testing | `risk/tests.py` |
| 3.17 ethics: coded IDs, no identifiers in logs, restricted access | `models.py`, `forms.py`, `settings.py` (logging), roles |

## Known limits

- Synthetic data and placeholder labels (see above). The selected demo model finds only about 4 in 10 high-risk cases in its synthetic test set, which shows why accuracy-style figures must never be trusted without local validation.
- Alert and referral wording is intentionally absent until MRRH obstetric staff review it.
- Formative usability testing with healthcare workers has not been done.
