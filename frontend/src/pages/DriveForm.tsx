import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, type User } from "../api";
import { useMeta } from "../meta";
import { ErrorBox } from "../ui";

const STREAMS = ["engineering", "polytechnic", "pharmacy", "management"];

const empty = {
  employer_name: "", title: "", stream: "engineering", job_family: "", description: "",
  institute_ids: [] as number[], programme_codes: [] as string[], branches: "", passing_years: "2027",
  min_cgpa: "", min_aggregate_pct: "", max_backlogs: "0", max_gap_years: "",
  required_skills: [] as string[], preferred_skills: [] as string[],
  w_required: "60", w_preferred: "20", w_context: "20", status: "open",
};

export default function DriveForm({ user }: { user: User }) {
  const meta = useMeta();
  const nav = useNavigate();
  const { id } = useParams();
  const [f, setF] = useState<any>({ ...empty, institute_ids: user.institute_id ? [user.institute_id] : [] });
  const [employerId, setEmployerId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    api(`/api/drives/${id}`).then((d: any) => {
      setEmployerId(d.employer.id);
      setF({
        ...empty, ...d, employer_name: d.employer.name, branches: d.branches.join(", "),
        passing_years: d.passing_years.join(", "), min_cgpa: d.min_cgpa ?? "", min_aggregate_pct: d.min_aggregate_pct ?? "",
        max_backlogs: d.max_backlogs ?? "", max_gap_years: d.max_gap_years ?? "",
        w_required: d.weights.required ?? "60", w_preferred: d.weights.preferred ?? "20", w_context: d.weights.context ?? "20",
      });
    });
  }, [id]);

  const families = meta?.job_families[f.stream] ?? {};
  const set = (k: string, v: any) => setF((x: any) => ({ ...x, [k]: v }));

  function pickFamily(fid: string) {
    const fam = families[fid];
    setF((x: any) => ({ ...x, job_family: fid, required_skills: fam ? fam.core : [], preferred_skills: fam ? fam.optional : [] }));
  }

  function toggle(list: string, v: any) {
    setF((x: any) => ({ ...x, [list]: x[list].includes(v) ? x[list].filter((y: any) => y !== v) : [...x[list], v] }));
  }

  async function save() {
    setError(null);
    const num = (v: any) => (v === "" || v === null ? null : Number(v));
    const custom = Number(f.w_required) !== 60 || Number(f.w_preferred) !== 20 || Number(f.w_context) !== 20;
    const body = {
      employer_id: employerId, employer_name: f.employer_name, title: f.title, stream: f.stream, job_family: f.job_family,
      description: f.description, institute_ids: f.institute_ids, programme_codes: f.programme_codes,
      branches: f.branches.split(",").map((s: string) => s.trim()).filter(Boolean),
      passing_years: String(f.passing_years).split(",").map((s: string) => Number(s.trim())).filter(Boolean),
      min_cgpa: num(f.min_cgpa), min_aggregate_pct: num(f.min_aggregate_pct), max_backlogs: num(f.max_backlogs),
      max_gap_years: num(f.max_gap_years), required_skills: f.required_skills, preferred_skills: f.preferred_skills,
      weights: custom ? { required: Number(f.w_required), preferred: Number(f.w_preferred), context: Number(f.w_context) } : {},
      status: f.status,
    };
    try {
      const d = await api(id ? `/api/drives/${id}` : "/api/drives", { method: id ? "PATCH" : "POST", json: body });
      nav(`/drives/${d.id}`);
    } catch (e: any) { setError(e.message); }
  }

  if (!meta) return null;
  const programmes = meta.programmes.filter((p) => p.stream === f.stream || f.programme_codes.includes(p.code) || (f.stream === "polytechnic" && p.code === "BTECH"));

  return (
    <>
      <h1>{id ? "Edit drive" : "New placement drive"}</h1>
      <p className="muted">Eligibility rules must be objective and job-related. Never use gender, category, religion, home town or photo.</p>
      <ErrorBox error={error} />
      <div className="card grid2">
        <div className="field"><label>Employer</label><input value={f.employer_name} disabled={!!id} onChange={(e) => set("employer_name", e.target.value)} /></div>
        <div className="field"><label>Drive title</label><input value={f.title} onChange={(e) => set("title", e.target.value)} /></div>
        <div className="field"><label>Stream</label>
          <select value={f.stream} onChange={(e) => setF({ ...f, stream: e.target.value, job_family: "", required_skills: [], preferred_skills: [], programme_codes: [] })}>
            {STREAMS.map((s) => <option key={s}>{s}</option>)}
          </select>
        </div>
        <div className="field"><label>Job family (sets default skills)</label>
          <select value={f.job_family} onChange={(e) => pickFamily(e.target.value)}>
            <option value="">Choose…</option>
            {Object.entries(families).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
        </div>
        <div className="field" style={{ gridColumn: "1 / -1" }}><label>Job description</label>
          <textarea rows={3} value={f.description} onChange={(e) => set("description", e.target.value)} />
        </div>
      </div>

      <div className="card">
        <h2>Eligibility gates</h2>
        <div className="grid3">
          <div className="field"><label>Institutes</label>
            {meta.institutes.map((i) => (
              <label key={i.id} className="row" style={{ color: "var(--ink)" }}>
                <input type="checkbox" style={{ width: "auto" }} checked={f.institute_ids.includes(i.id)}
                  disabled={user.role === "coordinator"} onChange={() => toggle("institute_ids", i.id)} /> {i.code}
              </label>
            ))}
          </div>
          <div className="field"><label>Programmes</label>
            {[...new Set(programmes.map((p) => p.code))].map((c) => (
              <label key={c} className="row" style={{ color: "var(--ink)" }}>
                <input type="checkbox" style={{ width: "auto" }} checked={f.programme_codes.includes(c)} onChange={() => toggle("programme_codes", c)} /> {c}
              </label>
            ))}
          </div>
          <div>
            <div className="field"><label>Branches (comma separated, blank = any)</label><input value={f.branches} onChange={(e) => set("branches", e.target.value)} /></div>
            <div className="field"><label>Passing years</label><input value={f.passing_years} onChange={(e) => set("passing_years", e.target.value)} /></div>
          </div>
          <div className="field"><label>Minimum CGPA</label><input type="number" step="0.1" value={f.min_cgpa} onChange={(e) => set("min_cgpa", e.target.value)} /></div>
          <div className="field"><label>Minimum aggregate %</label><input type="number" value={f.min_aggregate_pct} onChange={(e) => set("min_aggregate_pct", e.target.value)} /></div>
          <div className="field"><label>Max active backlogs</label><input type="number" value={f.max_backlogs} onChange={(e) => set("max_backlogs", e.target.value)} /></div>
        </div>
      </div>

      <div className="card">
        <h2>Skills to look for</h2>
        <p className="small muted">Click a skill to cycle: not used → required → preferred.</p>
        <div className="row">
          {Object.entries(meta.skills).map(([k, label]) => {
            const req = f.required_skills.includes(k), pref = f.preferred_skills.includes(k);
            return (
              <button key={k} type="button" className={req ? "primary" : ""} style={pref ? { borderColor: "var(--accent)", color: "var(--accent)" } : {}}
                onClick={() => {
                  if (req) setF({ ...f, required_skills: f.required_skills.filter((x: string) => x !== k), preferred_skills: [...f.preferred_skills, k] });
                  else if (pref) setF({ ...f, preferred_skills: f.preferred_skills.filter((x: string) => x !== k) });
                  else setF({ ...f, required_skills: [...f.required_skills, k] });
                }}>
                {label}{req ? " · req" : pref ? " · pref" : ""}
              </button>
            );
          })}
        </div>
        <h3 style={{ marginTop: 16 }}>Weights</h3>
        <div className="row">
          {[["w_required", "Required skills"], ["w_preferred", "Preferred skills"], ["w_context", "Project/JD relevance"]].map(([k, l]) => (
            <div key={k} style={{ width: 170 }}><label>{l}</label><input type="number" value={f[k]} onChange={(e) => set(k, e.target.value)} /></div>
          ))}
        </div>
        <p className="small muted">Changing the default 60/20/20 needs TPO approval before matching.</p>
      </div>
      <div className="row">
        <select value={f.status} onChange={(e) => set("status", e.target.value)} style={{ width: 140 }} aria-label="Status">
          <option>draft</option><option>open</option><option>closed</option>
        </select>
        <button className="primary" onClick={save}>Save drive</button>
      </div>
    </>
  );
}
