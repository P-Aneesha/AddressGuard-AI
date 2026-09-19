
# AddressGuard-AI
=======
# AddressGuard AI

**Intelligent Address Validation, Verification and Delivery Risk Assessment Platform**

AddressGuard AI takes messy, real-world delivery addresses — WhatsApp text,
courier labels, invoice copy-paste, OCR output, whatever — and runs them
through a 12-step, explainable, rule-based validation pipeline that
produces a confidence score, a separate risk rating, and one of four
final verdicts, with a human-in-the-loop step for every correction it
proposes.

This is **not** a simple form validator. It never overwrites what the
user typed without asking, it never claims to have physically verified
an address, and it never lets a clearly bad address "score its way" into
a VERIFIED status just because a lot of fields happen to be filled in.

---

## 1. Tech Stack

| Layer      | Technology |
|------------|------------|
| Frontend   | HTML5, CSS3, Vanilla JavaScript (no frameworks) |
| Backend    | Python 3, Flask |
| ORM        | SQLAlchemy (via Flask-SQLAlchemy) |
| Database   | PostgreSQL (Neon) — falls back to local SQLite if `DATABASE_URL` isn't set |
| Reports    | ReportLab (PDF), built-in `csv` module (CSV) |
| Codes      | `qrcode` (QR), `python-barcode` (Code128 barcode) |
| Auth       | Server-side sessions, Werkzeug password hashing (PBKDF2) |

No React, no Node.js, no MongoDB, no ML model training — exactly as specified.

---

## 1a. Accounts & Dashboard

The whole app now sits behind a login. Every page and every `/api/*`
endpoint requires a signed-in session.

- **`/register`** — create an account (username + password, email optional).
  Passwords are never stored in plain text, only a salted PBKDF2 hash.
- **`/login`** — sign in; **`/api/auth/logout`** — sign out.
- **`/dashboard`** — aggregate trust metrics: total validations run,
  average confidence, VERIFIED rate, a status/risk breakdown, and the
  most recent validations.

A note on "accuracy": there's no separate "accuracy: 100%" figure
tacked on anywhere. Confidence *is* the address's accuracy score —
inventing a second, always-perfect number alongside it would be
exactly the kind of overclaiming this project is built to avoid. What
changed is that the confidence engine itself was fixed so a genuinely
complete, correct address now honestly reaches 95-100%, instead of
being held down by an unrelated dataset-coverage gap (see the note
below).

---

## 2. How the Pipeline Works

```
Raw address text
      │
      ▼
Address Parser Service        → extracts name, phone, house no, street,
      │                          locality, city, state, PIN — field
      │                          order never matters
      ▼
Normalization Service         → AUTOMATIC SAFE fixes (spacing, casing,
      │                          "Rd"→"Road") applied immediately.
      │                          Meaning-changing fixes (e.g. "Hydrabad"
      │                          → "Hyderabad") are only ever SUGGESTED.
      ▼
Validation Pipeline           → phone / PIN / city-state / locality /
      │                          address-pattern checks, each with a
      │                          clearly labeled validation source
      ▼
Location Verification         → PIN↔city↔state↔locality cross-consistency
      ▼
Correction & Suggestion       → Original → Suggested → Reason → Confidence
      │
      ▼
[ USER: Accept / Reject / Manual Edit ]  ← nothing is auto-applied
      │
      ▼
Re-parse → Re-normalize → Re-validate → Re-score  (full loop, every time)
      │
      ▼
Confidence Engine             → evidence + penalties, then hard caps
      │
      ▼
Risk Engine                   → LOW / MEDIUM / HIGH / CRITICAL (independent
      │                          of confidence)
      ▼
Explainable Decision Engine   → VERIFIED / NEEDS CUSTOMER CONFIRMATION /
      │                          SUSPICIOUS / FAKE ADDRESS, with hard
      │                          rules able to override the raw score band
      ▼
Save record + generate QR / Barcode / PDF / CSV
```

### Confidence scoring

Positive evidence (name +5, valid phone +10, house number +10, street +10,
locality +15, city +15, state +10, valid PIN +20, PIN-location consistency
+10, valid pattern +5) minus penalties (wrong state −30, wrong city −25,
random text −50, missing city −30, etc.), clamped to `[0, 100]`, then
**hard-capped** — e.g. a missing house number can never score above 84,
and a PIN/city/state conflict can never reach VERIFIED, no matter how many
other fields look fine.

### Final status bands

| Score   | Status |
|---------|--------|
| 85–100  | VERIFIED *(only if no geographic conflicts and no missing core fields)* |
| 50–84   | NEEDS CUSTOMER CONFIRMATION |
| 20–49   | SUSPICIOUS |
| 0–19    | FAKE ADDRESS |

Hard rules always win over the score — random/meaningless text is always
FAKE ADDRESS regardless of score, and a PIN/city/state conflict can never
be VERIFIED.

---

## 3. Project Structure

```
AddressGuard-AI/
├── app.py                     # Flask app factory / entrypoint
├── config.py                  # env-driven configuration
├── requirements.txt
├── .env.example
├── README.md
├── models/
│   ├── __init__.py            # db instance
│   └── validation.py          # AddressValidation, ParsedAddressField,
│                               # CorrectionHistory, ValidationEvent, Report
├── services/
│   ├── address_parser.py
│   ├── normalizer.py
│   ├── phone_validator.py
│   ├── pin_validator.py
│   ├── location_verifier.py
│   ├── anomaly_detector.py
│   ├── correction_engine.py
│   ├── confidence_engine.py
│   ├── risk_engine.py
│   ├── decision_engine.py
│   ├── explainability_service.py   # orchestrates the full pipeline
│   └── report_service.py           # PDF / CSV / QR / barcode
├── routes/
│   ├── views.py                # serves the dashboard
│   └── api.py                  # /api/validate, /api/correction/<id>,
│                                # /api/history, /api/report/*
├── templates/
│   └── index.html
├── static/
│   ├── css/style.css
│   └── js/app.js
├── utils/
│   ├── indian_data.py           # offline states/cities/PIN dataset
│   └── timestamps.py            # UTC timezone-aware helpers
└── tests/
    └── test_pipeline.py
```

---

## 4. Setup Instructions

### 4.1 Clone and install

```bash
cd AddressGuard-AI
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4.2 Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```
DATABASE_URL=postgresql://user:password@your-neon-host/addressguard?sslmode=require
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
PUBLIC_BASE_URL=http://localhost:5000
```

> If you don't set `DATABASE_URL`, the app automatically falls back to a
> local SQLite file (`addressguard_dev.db`) so it still runs out of the box.

### 4.3 Run

```bash
python app.py
```

Visit **https://address-guard-ai-6se9.vercel.app/** — you'll land on the sign-in page first;
click **Create one** to register an account, which signs you in
immediately.

Tables are created automatically on first run via `db.create_all()`.

### 4.4 Run tests

```bash
python -m pytest tests/ -v
```

---

## 5. API Reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/validate` | Run the full pipeline on `{ "raw_text": "..." }` |
| POST | `/api/correction/<validation_id>` | Apply Accept/Reject/Manual-Edit decisions and re-validate |
| GET  | `/api/history?q=&status=` | Search/filter past validations |
| GET  | `/api/history/<validation_id>` | Full detail of one record |
| GET  | `/api/report/pdf/<validation_id>` | Download PDF report |
| GET  | `/api/report/csv/<validation_id>` | Download CSV export |
| GET  | `/api/report/qr/<validation_id>` | Get QR code (PNG) |
| GET  | `/api/report/barcode/<validation_id>` | Get Code128 barcode (PNG) |

---

## 6. Honesty & Explainability Notes

- **Phone validation** checks *format only* — the app never claims a
  number is confirmed to belong to a person.
- **Locality/PIN/city checks** are run against a bundled offline dataset
  (India Post postal-circle PIN prefixes + a curated city→state map), and
  every check result is labeled with its validation source
  (`FORMAT_VALIDATION`, `DATASET_VALIDATION`, `GEOGRAPHIC_CONSISTENCY_VALIDATION`)
  — the app never claims live external/physical verification it doesn't have.
- **No correction is ever applied silently.** Every suggestion (spelling,
  city/state alias) is shown with Original → Suggested → Reason →
  Confidence and requires an explicit Accept, Reject, or Manual Edit.
- **Every correction triggers a full re-parse and re-validation**, not a
  patch — so the confidence/risk/status you see always reflects the
  current working address, never stale data.

---

## 7. Known Limitations (good to mention in a viva/demo)

- The city/state/PIN dataset is curated for major Indian cities and
  postal circles — it will correctly say "not found in dataset" rather
  than guessing for smaller towns not included.
- Locality-level verification is heuristic (`LIKELY_MATCH`/`UNKNOWN`)
  since no verified locality-level open dataset is bundled — this is
  clearly surfaced in the UI rather than overstated.
- No live third-party geocoding API is called, by design, so the whole
  system works fully offline once dependencies are installed.
>>>>>>> 1657639 (Initial AddressGuard AI project)
