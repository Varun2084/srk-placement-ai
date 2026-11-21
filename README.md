# SRK Placement AI

This is an AI-assisted resume screening and placement platform for **Shri Rama Krishna Group, Satna**. It covers both institutes, SRKCESM and SRKCP, and all four streams: Engineering (B.Tech), Polytechnic (Diploma), Management (MBA) and Pharmacy (B.Pharm, D.Pharm).

> **AI assists, people decide.** The AI parses resumes, checks eligibility rules, maps evidence to drive criteria and explains its results. A placement coordinator records every shortlist decision with a reason. The TPO approves the shortlist, and an employer sees a student's profile only if that student has consented to share it with that employer.

This MVP follows the *SRK Group AI Resume Screening & Placement Intelligence Platform — Roadmap 2026*. It covers phases 1–4 of that roadmap, plus the core of phases 5 and 6.

## What works today

| Area | Features |
| --- | --- |
| **Students** | Accept a privacy notice (Hindi/English); under-18 students need guardian consent. Upload a PDF/DOCX/TXT resume. See exactly what was read from it and correct it. Get a readiness report for each job family, with a gap plan. Apply to drives. Give consent per employer before a profile is shared. |
| **Coordinators** (one institute) | See only their own institute's students. Verify academics against the college record. Create drives for their institute. Enrol students, run matching and review a ranked queue showing evidence, gates and confidence. Shortlist, hold or mark "not selected", with a reason that is required. |
| **TPO** (group-wide) | Everything a coordinator can do, across both institutes. Approve custom scoring weights. Approve shortlists, which are shared only with students who consented. View the dashboard, funnel and fairness monitor. Export a placements CSV for NAAC/NIRF. View the audit log. |
| **Employers** | See only their own drives, and only candidates who were approved and consented. Profiles show verified academics and skill evidence; contact details are hidden. Record interview, offer or not selected. |
| **AI pipeline** | Checks file type by magic bytes, with a basic active-content screen. Extracts text from PDF/DOCX. Splits the resume into sections and extracts fields, keeping the source span of each field. Normalises skills against 47 skills and 21 job families across 4 streams. Applies eligibility gates, where missing data is marked "verify" and never counted as a fail. Scores evidence, weighting projects and internships above skills that are only listed. Adds TF-IDF project/JD relevance and template explanations, and flags prompt-injection text. |
| **Accounts** | Admin/TPO create staff and employer accounts. Bulk-import students from a college CSV (academics marked verified) and get a CSV of login passwords. Coordinators can reset their own students' passwords; everyone can change their own. |
| **Governance** | Immutable audit events for logins, views, uploads, match runs, decisions, approvals and exports. Each match run is versioned (rubric, parser, taxonomy, drive version). Overrides are detected and counted. A four-fifths fairness flag watches shortlist rates by group. Protected attributes are never collected or used. |

It is fully local: no paid AI API is needed. `app/ai/providers.py` has adapters so you can plug in sentence-transformers, Claude or another LLM later.

## Run it

### Laptop par check karna (sabse aasaan)

1. [Docker Desktop](https://www.docker.com/products/docker-desktop/) install karein aur kholein.
2. GitHub par **Code → Download ZIP** karein aur ZIP ko unzip karein (ya `git clone` karein).
3. **Windows:** folder mein `start.bat` par double-click karein. **Mac/Linux:** `bash start.sh`.
4. 5–10 minute baad browser mein `http://localhost:8080` apne aap khul jaayega. Demo logins neeche table mein hain.

Band karna ho to `docker compose stop`, dobara chalana ho to `docker compose start` (ya `start.bat` phir se).

### VS Code mein chalana (bina Docker)

Zaroorat: [Python 3.11+](https://www.python.org/downloads/) (Windows par install karte waqt *Add to PATH* tick karein), [Node.js 20+](https://nodejs.org/) aur VS Code.

1. VS Code mein **File → Open Folder** se `srk-placement-ai` folder kholein. Recommended extensions (Python) install karne ka popup aaye to *Install* karein.
2. **Terminal → Run Task… → `1. Setup (first time)`**. Yeh Python packages aur npm packages install karta hai, aur demo data bharta hai. Sirf ek baar karna hai.
3. **Terminal → Run Task… → `2. Run app (backend + frontend)`**. Backend aur frontend dono chalu ho jaayenge.
4. Browser mein **http://localhost:5173** kholein. Code badlenge to page apne aap refresh ho jaayega.

Debug karna ho (breakpoints) to **Run and Debug** (Ctrl+Shift+D) mein **Full stack (debug)** chunein. Tests chalane ke liye **Run Task → `Test: backend (pytest)`** chalaayein. Database `backend/srk_placement.db` (SQLite) mein rehta hai. Demo data dobara bharna ho to **Run Task → `Seed demo data`** chalaayein.

### Option A — College server with Docker (one command)

On any Ubuntu 24.04 PC on the college network:

```bash
sudo bash deploy/install.sh          # demo data
sudo bash deploy/install.sh --real   # empty database + admin account, for real students
```

This installs Docker, generates secrets, starts the app with Postgres (it restarts itself after reboots), and sets up nightly backups. **Full Hinglish guide:** [docs/COLLEGE_SERVER_SETUP.md](docs/COLLEGE_SERVER_SETUP.md). It also covers access from outside the campus via Cloudflare Tunnel, CSV import of students, Windows, backups and troubleshooting.

### Option B — local development

```bash
# backend
cd backend
pip install -r requirements-dev.txt
python seed.py --reset                     # synthetic demo data (SQLite)
uvicorn app.main:app --reload --port 8000  # API docs at http://localhost:8000/docs

# frontend (second terminal)
cd frontend
npm install
npm run dev                                # http://localhost:5173
```

### Demo accounts (password `Srk@2026`, synthetic data only)

| Role | Email |
| --- | --- |
| Central TPO | `tpo@srk.demo` |
| Coordinator, SRKCESM | `coord.esm@srk.demo` |
| Coordinator, SRKCP | `coord.cp@srk.demo` |
| Student | `student001@srk.demo` |
| Employer (IT) | `hr@vindhyainfotech.demo` |
| Employer (Pharma) | `hr@satnapharma.demo` |
| Admin | `admin@srk.demo` |

The `samples/` folder has a B.Pharm PDF and a B.Tech DOCX resume you can try uploading.

## Demo walkthrough (10 minutes)

1. Log in as **TPO** → **Drives** → *Graduate Engineer Trainee – Software*. Open a row to see the evidence snippets, the gates and the score breakdown.
2. Log in as **Coordinator SRKCESM**. Shortlist two students, each with a reason. Try to open an SRKCP student: access is blocked.
3. Log in as one of those **students** (find their email under TPO → Students) → **Placement drives**. Tick *Allow sharing my profile with this employer*.
4. Log in as **TPO** and click **Approve shortlist**. Profiles go only to students who consented.
5. Log in as **Employer (IT)**. You'll see only the shared candidates, with no phone or email. Record an interview or offer.
6. Log in as **TPO** → **Dashboard** to see the funnel and fairness monitor, then **Audit log** to see every step above.

## Project layout

```
backend/
  app/
    ai/            extract.py (files), parser.py (sections/fields/skills), matcher.py (gates+score+explain),
                   readiness.py, providers.py (swappable similarity / LLM), taxonomy.py
    data/taxonomy.json   skills, aliases, related skills, job families per stream — edit with domain leads
    routers/       auth, students, drives (queue/review/approval/employer), reports (+audit)
    models.py      institutes, programmes, students, resumes, evidence, drives, match runs, reviews, consent, audit
    security.py    JWT auth, roles, institute scoping
    services.py    resume processing and match runs
  seed.py          synthetic demo data
  tests/           18 tests: parser, gates, scoring, isolation, consent, overrides, approvals, reports
frontend/          React + TypeScript (Vite); student, coordinator, TPO, employer screens
samples/           synthetic resumes for upload testing
```

## Before using real student data

These are release gates from the roadmap. The code supports them, but people have to do them:

- [ ] Legal/DPDP review of the consent text, retention period, grievance officer and employer data-sharing terms.
- [ ] Use `install.sh --real` (strong secrets, Postgres, nightly backups), test a restore, and use HTTPS (Cloudflare Tunnel) for access from outside the campus.
- [ ] Add a real malware scanner (e.g. ClamAV) and OCR for scanned resumes (`extract.py` has the hooks).
- [ ] Domain leads review `taxonomy.json` for their stream, and build a gold-labelled evaluation set.
- [ ] Run accessibility review, load test and an external penetration test.
- [ ] Retention job: delete or anonymise alumni data after the agreed period.
- [ ] SSO / ERP integration, if the college has one.

## Next on the roadmap

OCR (Tesseract) · ERP import of verified academics · SSO · SMS/WhatsApp notifications · interview scheduling and scorecards · optional LLM explanations through `providers.py` · per-stream AI evaluation reports · retention/deletion automation.
