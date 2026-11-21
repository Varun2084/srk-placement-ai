import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type User } from "../api";
import { useMeta } from "../meta";
import { ErrorBox, Pill } from "../ui";

export default function Students({ user }: { user: User }) {
  const meta = useMeta();
  const nav = useNavigate();
  const [rows, setRows] = useState<any[]>([]);
  const [prog, setProg] = useState("");
  const [inst, setInst] = useState("");
  const [q, setQ] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const p = new URLSearchParams();
    if (prog) p.set("programme", prog);
    if (inst) p.set("institute_id", inst);
    if (q) p.set("q", q);
    api<any[]>(`/api/students?${p}`).then(setRows).catch((e) => setError(e.message));
  }, [prog, inst, q]);

  const progs = [...new Set(meta?.programmes.map((p) => p.code) ?? [])];

  return (
    <>
      <h1>Students</h1>
      <p className="muted">{user.role === "coordinator" ? "Students of your institute only." : "All institutes."} Click a student to verify academics and see the parsed resume.</p>
      <div className="row card">
        {user.role !== "coordinator" && (
          <select value={inst} onChange={(e) => setInst(e.target.value)} style={{ width: 180 }} aria-label="Institute">
            <option value="">All institutes</option>
            {meta?.institutes.map((i) => <option key={i.id} value={i.id}>{i.code}</option>)}
          </select>
        )}
        <select value={prog} onChange={(e) => setProg(e.target.value)} style={{ width: 180 }} aria-label="Programme">
          <option value="">All programmes</option>
          {progs.map((p) => <option key={p}>{p}</option>)}
        </select>
        <input placeholder="Search name or roll no." value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 260 }} />
        <span className="muted small">{rows.length} students</span>
      </div>
      <ErrorBox error={error} />
      <div className="card">
        <table>
          <thead><tr><th>Name</th><th>Roll no.</th><th>Institute</th><th>Programme</th><th>Branch</th><th>CGPA / %</th><th>Resume</th><th>Status</th></tr></thead>
          <tbody>
            {rows.map((s) => (
              <tr key={s.id} className="clickable" onClick={() => nav(`/students/${s.id}`)}>
                <td>{s.name}</td><td>{s.roll_no}</td><td>{s.institute}</td><td>{s.programme}</td><td>{s.branch}</td>
                <td>{s.cgpa ?? (s.aggregate_pct ? `${s.aggregate_pct}%` : "—")}</td>
                <td>{s.resume_status === "parsed" ? `${s.skills_count} skills` : <span className="muted">{s.resume_status}</span>}</td>
                <td className="row">
                  {!s.consent && <Pill kind="warn">No consent</Pill>}
                  {s.academics_verified ? <Pill kind="good">Verified</Pill> : <Pill kind="warn">Unverified</Pill>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
