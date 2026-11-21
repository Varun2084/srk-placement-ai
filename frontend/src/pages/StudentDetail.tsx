import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, download, type User } from "../api";
import { Bar, ErrorBox, Pill } from "../ui";

const NUM_FIELDS: [string, string][] = [
  ["cgpa", "CGPA (0-10)"], ["aggregate_pct", "Aggregate %"], ["active_backlogs", "Active backlogs"],
  ["tenth_pct", "10th %"], ["twelfth_pct", "12th %"], ["gap_years", "Gap years"], ["passing_year", "Passing year"],
];

export default function StudentDetail({ user: _user }: { user: User }) {
  const { id } = useParams();
  const [s, setS] = useState<any>(null);
  const [ready, setReady] = useState<any>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  async function load() {
    const st = await api(`/api/students/${id}`);
    setS(st);
    const f: Record<string, string> = { branch: st.branch ?? "" };
    NUM_FIELDS.forEach(([k]) => {
      f[k] = st[k] ?? (st.declared?.[k] !== undefined ? String(st.declared[k]) : "");
    });
    setForm(f);
    if (st.resume) setReady(await api(`/api/students/${id}/readiness`));
  }
  useEffect(() => { load().catch((e) => setError(e.message)); }, [id]);

  async function verify() {
    setError(null); setMsg(null);
    const body: Record<string, any> = { branch: form.branch, verified: true };
    NUM_FIELDS.forEach(([k]) => { if (form[k] !== "") body[k] = Number(form[k]); });
    try {
      await api(`/api/students/${id}/academics`, { method: "PATCH", json: body });
      setMsg("Academic record saved and marked verified.");
      load();
    } catch (e: any) { setError(e.message); }
  }

  if (!s) return <ErrorBox error={error} />;
  return (
    <>
      <div className="topline">
        <div>
          <h1>{s.name}</h1>
          <div className="muted">{s.roll_no} · {s.programme_name} · {s.branch} · {s.institute} · {s.email}</div>
        </div>
        <div className="row">
          {s.consent ? <Pill kind="good">Consent given</Pill> : <Pill kind="warn">No consent</Pill>}
          {s.academics_verified ? <Pill kind="good">Verified</Pill> : <Pill kind="warn">Unverified</Pill>}
        </div>
      </div>
      <ErrorBox error={error} />
      {msg && <div className="ok">{msg}</div>}
      <div className="grid2">
        <div className="card">
          <h2>Verify academic record</h2>
          <p className="small muted">Check against the college ERP / marksheets. Values prefilled from the resume are student-declared until you save.</p>
          <div className="field"><label>Branch</label><input value={form.branch ?? ""} onChange={(e) => setForm({ ...form, branch: e.target.value })} /></div>
          <div className="grid2" style={{ gap: 10 }}>
            {NUM_FIELDS.map(([k, l]) => (
              <div className="field" key={k}>
                <label htmlFor={k}>{l}</label>
                <input id={k} type="number" step="0.01" value={form[k] ?? ""} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
              </div>
            ))}
          </div>
          <button className="good" onClick={verify}>Save as verified</button>
        </div>
        <div className="card">
          <h2>Parsed resume</h2>
          {!s.resume ? <p className="muted">No parsed resume yet.</p> : (
            <>
              <p className="small muted">
                {s.resume.filename} · parser {s.resume.parser_version} · language {s.resume.language}{" "}
                <a href="#" onClick={(e) => { e.preventDefault(); download(`/api/resumes/${s.resume.id}/file`, s.resume.filename); }}>download original</a>
              </p>
              {s.resume.injection_flag && <div className="notice">Contains instruction-like text aimed at screening software. Review manually.</div>}
              <table><tbody>
                {s.resume.fields.map((f: any) => (
                  <tr key={f.id}><td>{f.field}</td><td>{f.value}</td><td className="small muted">{Math.round(f.confidence * 100)}%{f.verified ? " · verified" : ""}</td></tr>
                ))}
              </tbody></table>
              <h3 style={{ marginTop: 12 }}>Skill evidence</h3>
              {s.resume.skills.map((k: any, i: number) => (
                <div className="evidence evidenced" key={i}><strong>{k.label}</strong> <span className="muted small">· {k.section}</span><div className="snippet">“{k.snippet}”</div></div>
              ))}
            </>
          )}
        </div>
      </div>
      {ready && (
        <div className="card">
          <h2>Readiness by job family</h2>
          <table>
            <thead><tr><th>Job family</th><th style={{ width: "40%" }}>Readiness</th><th>Top gaps</th></tr></thead>
            <tbody>
              {ready.families.map((f: any) => (
                <tr key={f.job_family}>
                  <td>{f.label}</td>
                  <td><div className="row"><span style={{ flex: 1 }}><Bar value={f.readiness_pct} /></span><span className="score">{f.readiness_pct}%</span></div></td>
                  <td className="small">{f.gaps.filter((g: any) => g.priority === "core").map((g: any) => g.skill).join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
