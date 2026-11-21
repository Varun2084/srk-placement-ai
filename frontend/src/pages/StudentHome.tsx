import { useEffect, useState } from "react";
import { api } from "../api";
import { useT } from "../i18n";
import { Bar, ErrorBox, Pill } from "../ui";

const FIELD_LABEL: Record<string, string> = {
  name: "Name", email: "Email", phone: "Phone", cgpa: "CGPA", tenth_pct: "10th %", twelfth_pct: "12th %",
  aggregate_pct: "Aggregate %", passing_year: "Passing year", active_backlogs: "Active backlogs",
};

export default function StudentHome() {
  const { t } = useT();
  const [me, setMe] = useState<any>(null);
  const [ready, setReady] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [edit, setEdit] = useState<Record<number, string>>({});

  async function load() {
    const m = await api("/api/students/me");
    setMe(m);
    if (m.resume) setReady(await api(`/api/students/${m.id}/readiness`));
  }
  useEffect(() => { load().catch((e) => setError(e.message)); }, []);

  async function consent(granted: boolean) {
    setError(null);
    try {
      setMe(await api(`/api/students/${me.id}/consent`, { method: "POST", json: { granted } }));
    } catch (e: any) { setError(e.message); }
  }

  async function upload(file: File) {
    setBusy(true); setError(null); setMsg(null);
    const fd = new FormData();
    fd.append("file", file);
    try {
      await api(`/api/students/${me.id}/resume`, { method: "POST", body: fd });
      setMsg("Resume processed. Check the details below.");
      await load();
    } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  }

  async function saveField(fid: number) {
    try {
      await api(`/api/resumes/${me.resume.id}/fields/${fid}`, { method: "PATCH", json: { value: edit[fid] } });
      setEdit((x) => { const y = { ...x }; delete y[fid]; return y; });
      await load();
    } catch (e: any) { setError(e.message); }
  }

  if (!me) return <ErrorBox error={error} />;

  return (
    <>
      <div className="topline">
        <div>
          <h1>{me.name}</h1>
          <div className="muted">{me.programme_name} · {me.branch} · {me.institute} · Batch {me.passing_year}</div>
        </div>
        {me.academics_verified ? <Pill kind="good">Academics verified</Pill> : <Pill kind="warn">Academics not yet verified</Pill>}
      </div>
      <ErrorBox error={error} />
      {msg && <div className="ok">{msg}</div>}

      {!me.consent ? (
        <div className="card">
          <h2>{t("consentTitle")}</h2>
          <p>{t("consentText")}</p>
          {me.is_minor && <p className="notice">You are under 18: a parent or guardian must also agree before your data is processed.</p>}
          <button className="primary" onClick={() => consent(true)}>{t("accept")}</button>
        </div>
      ) : (
        <div className="grid2">
          <div className="card">
            <h2>{t("uploadResume")}</h2>
            <input type="file" accept=".pdf,.docx,.txt" disabled={busy} aria-label="Resume file"
              onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
            {busy && <p className="muted">Processing…</p>}
            {me.resume && (
              <p className="small muted">Current: {me.resume.filename} · parsed {new Date(me.resume.uploaded_at).toLocaleDateString()} · {me.skills_count} skills found</p>
            )}
            <p className="small"><a href="#" onClick={(e) => { e.preventDefault(); consent(false); }}>{t("withdraw")}</a></p>
          </div>
          <div className="card">
            <h2>College record</h2>
            <table><tbody>
              <tr><td>CGPA</td><td>{me.cgpa ?? "—"}</td></tr>
              <tr><td>Aggregate %</td><td>{me.aggregate_pct ?? "—"}</td></tr>
              <tr><td>Active backlogs</td><td>{me.active_backlogs ?? "—"}</td></tr>
            </tbody></table>
            <p className="small muted">Set by your placement coordinator from the college record. Ask them if something is wrong.</p>
          </div>
        </div>
      )}

      {me.resume && (
        <div className="card">
          <h2>{t("extracted")}</h2>
          {me.resume.injection_flag && <div className="notice">Your resume contains text addressed to screening software. It will be reviewed manually.</div>}
          <table>
            <thead><tr><th>Field</th><th>Value</th><th>Read from</th><th></th></tr></thead>
            <tbody>
              {me.resume.fields.map((f: any) => (
                <tr key={f.id}>
                  <td>{FIELD_LABEL[f.field] ?? f.field}</td>
                  <td>
                    {edit[f.id] !== undefined ? (
                      <input value={edit[f.id]} onChange={(e) => setEdit({ ...edit, [f.id]: e.target.value })} aria-label={`Correct ${f.field}`} />
                    ) : f.value}
                  </td>
                  <td className="snippet small">{f.snippet}</td>
                  <td>
                    {edit[f.id] !== undefined
                      ? <button onClick={() => saveField(f.id)}>Save</button>
                      : <button className="ghost" onClick={() => setEdit({ ...edit, [f.id]: f.value })}>Correct</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {ready && (
        <div className="card">
          <h2>{t("readiness")}</h2>
          <p className="small muted">{ready.note}</p>
          {ready.families.map((f: any) => (
            <details key={f.job_family} style={{ marginBottom: 10 }}>
              <summary style={{ cursor: "pointer" }}>
                <span style={{ display: "inline-flex", gap: 12, alignItems: "center", width: "calc(100% - 20px)" }}>
                  <span style={{ width: 300, flex: "none" }}>{f.label}</span>
                  <span style={{ flex: 1 }}><Bar value={f.readiness_pct} /></span>
                  <span className="score">{f.readiness_pct}%</span>
                  <Pill kind={f.band === "ready" ? "good" : f.band === "developing" ? "warn" : "bad"}>{f.band}</Pill>
                </span>
              </summary>
              <div style={{ padding: "8px 0 0 16px" }}>
                <h3>{t("gaps")}</h3>
                {f.gaps.length === 0 ? <p className="muted">Nothing major — keep your resume updated.</p> : (
                  <ul>
                    {f.gaps.map((g: any) => (
                      <li key={g.skill}><strong>{g.skill}</strong> <span className="muted small">({g.priority}, {g.status.replace("_", " ")})</span>: {g.action}</li>
                    ))}
                  </ul>
                )}
              </div>
            </details>
          ))}
        </div>
      )}
    </>
  );
}
