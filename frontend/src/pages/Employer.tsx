import { useEffect, useState } from "react";
import { api, download } from "../api";
import { ErrorBox, Pill, StatusPill } from "../ui";

export default function Employer() {
  const [drives, setDrives] = useState<any[]>([]);
  const [sel, setSel] = useState<number | null>(null);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<any[]>("/api/drives").then((d) => { setDrives(d); if (d[0]) setSel(d[0].id); }).catch((e) => setError(e.message));
  }, []);
  const load = () => sel && api(`/api/employer/drives/${sel}/candidates`).then(setData).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [sel]);

  async function stage(aid: number, status: string) {
    try { await api(`/api/applications/${aid}/stage`, { method: "POST", json: { status } }); load(); } catch (e: any) { setError(e.message); }
  }

  return (
    <>
      <h1>Shared candidates</h1>
      <p className="muted">Profiles appear here only after the college TPO approves them and the student agrees to share with your organisation.</p>
      <ErrorBox error={error} />
      <div className="row card">
        <label htmlFor="drive" style={{ margin: 0 }}>Drive</label>
        <select id="drive" value={sel ?? ""} onChange={(e) => setSel(Number(e.target.value))} style={{ width: 360 }}>
          {drives.map((d) => <option key={d.id} value={d.id}>{d.title}</option>)}
        </select>
      </div>
      {data && data.candidates.length === 0 && <div className="card muted">No candidates shared yet for this drive.</div>}
      {data?.candidates.map((c: any) => (
        <div className="card" key={c.application_id}>
          <div className="topline" style={{ marginBottom: 6 }}>
            <div>
              <h2 style={{ marginBottom: 2 }}>{c.name}</h2>
              <div className="muted">{c.programme} · {c.branch} · {c.institute} · Batch {c.passing_year}</div>
            </div>
            <StatusPill status={c.status} />
          </div>
          <div className="row small" style={{ marginBottom: 8 }}>
            {c.academics_verified ? <Pill kind="good">College-verified academics</Pill> : <Pill kind="warn">Academics unverified</Pill>}
            {c.cgpa != null && <Pill>CGPA {c.cgpa}</Pill>}
            {c.aggregate_pct != null && <Pill>Aggregate {c.aggregate_pct}%</Pill>}
          </div>
          {c.evidence.map((e: any) => (
            <div key={e.skill} className={`evidence ${e.status}`}><strong>{e.label}</strong> <span className="muted small">· {e.section}</span><div className="snippet">“{e.snippet}”</div></div>
          ))}
          <div className="row" style={{ marginTop: 10 }}>
            {c.resume_id && <button onClick={() => download(`/api/resumes/${c.resume_id}/file`, `${c.name}.resume`)}>Download resume</button>}
            <button onClick={() => stage(c.application_id, "interview")}>Mark interview</button>
            <button className="good" onClick={() => stage(c.application_id, "offered")}>Record offer</button>
            <button onClick={() => stage(c.application_id, "not_selected")}>Not selected</button>
          </div>
        </div>
      ))}
    </>
  );
}
