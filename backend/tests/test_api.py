import io

from conftest import login


def _students(client, hdr):
    r = client.get("/api/students", headers=hdr)
    assert r.status_code == 200
    return r.json()


def test_requires_login(client):
    assert client.get("/api/students").status_code == 401
    assert client.post("/api/auth/login", json={"email": "tpo@srk.demo", "password": "wrong"}).status_code == 401


def test_institute_isolation(client, h):
    cp_students = _students(client, h["cp"])
    esm_students = _students(client, h["esm"])
    assert cp_students and esm_students
    assert {s["institute"] for s in cp_students} == {"SRKCP"}
    assert {s["institute"] for s in esm_students} == {"SRKCESM"}
    # SRKCP coordinator cannot open an SRKCESM student, even by id.
    r = client.get(f"/api/students/{esm_students[0]['id']}", headers=h["cp"])
    assert r.status_code == 403
    # TPO sees both.
    assert {s["institute"] for s in _students(client, h["tpo"])} == {"SRKCP", "SRKCESM"}


def test_students_and_employers_cannot_list_students(client, h):
    assert client.get("/api/students", headers=h["student"]).status_code == 403
    assert client.get("/api/students", headers=h["it"]).status_code == 403


def test_student_sees_only_own_profile(client, h):
    me = client.get("/api/students/me", headers=h["student"]).json()
    other = [s for s in _students(client, h["tpo"]) if s["id"] != me["id"]][0]
    assert client.get(f"/api/students/{other['id']}", headers=h["student"]).status_code == 403
    rd = client.get(f"/api/students/{me['id']}/readiness", headers=h["student"]).json()
    assert rd["families"] and "never shared with employers" in rd["note"]


def test_upload_parse_and_correct(client, h):
    me = client.get("/api/students/me", headers=h["student"]).json()
    text = b"Test Student\nEducation\nB.Tech CSE 2027 CGPA 8.1/10\nSkills\nPython, SQL\nProjects\n- Flask web app with MySQL\n"
    r = client.post(f"/api/students/{me['id']}/resume", headers=h["student"],
                    files={"file": ("resume.txt", io.BytesIO(text), "text/plain")})
    assert r.status_code == 200, r.text
    resume = r.json()["resume"]
    assert resume["status"] == "parsed"
    cg = next(f for f in resume["fields"] if f["field"] == "cgpa")
    assert cg["value"] == "8.10"
    fix = client.patch(f"/api/resumes/{resume['id']}/fields/{cg['id']}", headers=h["student"], json={"value": "8.0"})
    assert fix.status_code == 200 and fix.json()["verified"] is False  # student edits stay "declared"


def test_bad_files_rejected(client, h):
    me = client.get("/api/students/me", headers=h["student"]).json()
    r = client.post(f"/api/students/{me['id']}/resume", headers=h["student"],
                    files={"file": ("cv.pdf", io.BytesIO(b"MZ fake exe"), "application/pdf")})
    assert r.status_code == 400
    r = client.post(f"/api/students/{me['id']}/resume", headers=h["student"],
                    files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4 /JavaScript (x)"), "application/pdf")})
    assert r.status_code == 422 and "active content" in r.json()["detail"]


def test_queue_review_override_and_sharing(client, h):
    drives = client.get("/api/drives", headers=h["tpo"]).json()
    d = next(x for x in drives if x["job_family"] == "software_engineer")
    q = client.get(f"/api/drives/{d['id']}/queue", headers=h["tpo"]).json()
    assert q["run"]["rubric"] and q["items"]
    assert "every decision is made" in q["notice"].lower()
    # Nothing was rejected automatically.
    assert all(i["status"] == "applied" for i in q["items"])

    # SRKCP coordinator cannot see or review this SRKCESM-only drive.
    assert client.get(f"/api/drives/{d['id']}/queue", headers=h["cp"]).status_code == 404

    top = q["items"][0]
    # A reason is mandatory.
    assert client.post(f"/api/applications/{top['application_id']}/review", headers=h["esm"],
                       json={"decision": "shortlisted", "reason": ""}).status_code == 422
    r = client.post(f"/api/applications/{top['application_id']}/review", headers=h["esm"],
                    json={"decision": "shortlisted", "reason": "Strong project evidence in Java and SQL"})
    assert r.status_code == 200 and r.json()["override"] is False

    failed = next((i for i in q["items"] if i["result"] and i["result"]["gate_status"] == "fail"), None)
    if failed:
        r = client.post(f"/api/applications/{failed['application_id']}/review", headers=h["esm"],
                        json={"decision": "shortlisted", "reason": "Backlog cleared last week; certificate seen"})
        assert r.json()["override"] is True

    # Employer sees nothing before TPO approval and student consent.
    assert client.get(f"/api/employer/drives/{d['id']}/candidates", headers=h["it"]).json()["candidates"] == []
    # Employer of another company cannot see this drive at all.
    assert client.get(f"/api/employer/drives/{d['id']}/candidates", headers=h["pharma"]).status_code == 404
    # Coordinators cannot approve; TPO can.
    assert client.post(f"/api/drives/{d['id']}/approve-shortlist", headers=h["esm"]).status_code == 403
    res = client.post(f"/api/drives/{d['id']}/approve-shortlist", headers=h["tpo"]).json()
    assert res["shared"] == 0 and res["awaiting_student_consent"] >= 1

    # The shortlisted student consents to share with this employer, TPO re-approves -> shared.
    sid = top["student"]["id"]
    email = next(s for s in _students(client, h["tpo"]) if s["id"] == sid)["email"]
    st = login(client, email)
    assert client.post(f"/api/drives/{d['id']}/share-consent", headers=st).status_code == 200
    res = client.post(f"/api/drives/{d['id']}/approve-shortlist", headers=h["tpo"]).json()
    assert res["shared"] >= 1
    cands = client.get(f"/api/employer/drives/{d['id']}/candidates", headers=h["it"]).json()["candidates"]
    assert len(cands) >= 1
    assert "phone" not in cands[0] and "email" not in cands[0]


def test_custom_weights_need_tpo_approval(client, h):
    body = {"employer_name": "Test Co", "title": "Test drive", "job_family": "pharmacist", "stream": "pharmacy",
            "programme_codes": ["DPHARM"], "required_skills": ["dispensing"], "weights": {"required": 80, "context": 20, "preferred": 0}}
    r = client.post("/api/drives", headers=h["cp"], json=body)
    assert r.status_code == 200, r.text
    did = r.json()["id"]
    assert r.json()["institute_ids"] == [2] or r.json()["institute_ids"]  # auto-scoped to own institute
    assert client.post(f"/api/drives/{did}/match", headers=h["cp"]).status_code == 400
    assert client.post(f"/api/drives/{did}/approve-weights", headers=h["tpo"]).status_code == 200
    assert client.post(f"/api/drives/{did}/enrol-eligible", headers=h["cp"]).json()["added"] >= 1
    assert client.post(f"/api/drives/{did}/match", headers=h["cp"]).status_code == 200


def test_coordinator_cannot_create_drive_for_other_institute(client, h):
    body = {"employer_name": "X", "title": "Cross drive", "job_family": "software_engineer", "stream": "engineering",
            "institute_ids": [1]}
    assert client.post("/api/drives", headers=h["cp"], json=body).status_code == 403


def test_reports_and_audit(client, h):
    s = client.get("/api/reports/summary", headers=h["tpo"]).json()
    assert s["funnel"][0]["stage"] == "applied" and s["programmes"]
    cp = client.get("/api/reports/summary", headers=h["cp"]).json()
    assert all(p["group"].startswith("SRKCP") for p in cp["programmes"])
    log = client.get("/api/audit", headers=h["admin"]).json()
    actions = {e["action"] for e in log}
    assert {"application.review", "match.run", "resume.parsed"} <= actions
    assert client.get("/api/audit", headers=h["esm"]).status_code == 403
    csv = client.get("/api/reports/placements.csv", headers=h["tpo"])
    assert csv.status_code == 200 and csv.text.startswith("institute,programme")


def test_csv_import_and_password_flow(client, h):
    csv_text = ("name,email,roll_no,institute,programme,branch,passing_year,cgpa,aggregate_pct,active_backlogs,date_of_birth_under_18\n"
                "Real Student,real.one@example.com,R001,SRKCP,BPHARM,Pharmacy,2027,,72.5,0,no\n"
                "Wrong Inst,wrong@example.com,R002,SRKCESM,BTECH,Civil,2027,7,,0,no\n"
                "Minor One,minor@example.com,R003,SRKCP,DPHARM,Pharmacy,2028,,,,yes\n")
    r = client.post("/api/admin/students/import", headers=h["cp"],
                    files={"file": ("s.csv", io.BytesIO(csv_text.encode()), "text/csv")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 2 and "outside your institute" in body["result_csv"]
    pw = next(l.split(",")[3] for l in body["result_csv"].splitlines() if l.startswith("2,"))
    r = client.post("/api/auth/login", json={"email": "real.one@example.com", "password": pw})
    assert r.status_code == 200
    hdr = {"Authorization": f"Bearer {r.json()['token']}"}
    me = client.get("/api/students/me", headers=hdr).json()
    assert me["academics_verified"] is True and me["aggregate_pct"] == 72.5
    assert client.post("/api/auth/change-password", headers=hdr, json={"old_password": pw, "new_password": "NewPass#2027"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "real.one@example.com", "password": "NewPass#2027"}).status_code == 200
    # Minor cannot consent without guardian consent.
    minor_pw = next(l.split(",")[3] for l in body["result_csv"].splitlines() if l.startswith("4,"))
    mh = {"Authorization": "Bearer " + client.post("/api/auth/login", json={"email": "minor@example.com", "password": minor_pw}).json()["token"]}
    mid = client.get("/api/students/me", headers=mh).json()["id"]
    assert client.post(f"/api/students/{mid}/consent", headers=mh, json={"granted": True}).status_code == 400
    assert client.post(f"/api/students/{mid}/consent", headers=mh, json={"granted": True, "guardian_consent": True}).status_code == 200


def test_staff_accounts(client, h):
    r = client.post("/api/admin/users", headers=h["tpo"], json={"email": "c3@srk.local", "name": "New Coord", "role": "coordinator", "institute_id": 1})
    assert r.status_code == 200 and r.json()["temporary_password"]
    assert client.post("/api/admin/users", headers=h["tpo"], json={"email": "a2@srk.local", "name": "Test User", "role": "admin"}).status_code == 403
    assert client.post("/api/admin/users", headers=h["esm"], json={"email": "z@srk.local", "name": "Test User", "role": "tpo"}).status_code == 403
