import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type User } from "../api";
import { useMeta } from "../meta";
import { ErrorBox, Pill } from "../ui";

export default function Drives({ user: _user }: { user: User }) {
  const meta = useMeta();
  const nav = useNavigate();
  const [drives, setDrives] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api<any[]>("/api/drives").then(setDrives).catch((e) => setError(e.message)); }, []);
  const inst = (ids: number[]) => ids.map((i) => meta?.institutes.find((x) => x.id === i)?.code ?? i).join(", ") || "All";

  return (
    <>
      <div className="topline">
        <div>
          <h1>Placement drives</h1>
          <p className="muted" style={{ margin: 0 }}>Each drive has its own eligibility rules and skill criteria. Open one to run matching and review.</p>
        </div>
        <Link to="/drives/new"><button className="primary">New drive</button></Link>
      </div>
      <ErrorBox error={error} />
      <div className="card">
        <table>
          <thead><tr><th>Drive</th><th>Employer</th><th>Stream</th><th>Institutes</th><th>Programmes</th><th>Applicants</th><th>Status</th></tr></thead>
          <tbody>
            {drives.map((d) => {
              const total = Object.values(d.counts as Record<string, number>).reduce((a, b) => a + b, 0);
              return (
                <tr key={d.id} className="clickable" onClick={() => nav(`/drives/${d.id}`)}>
                  <td><strong>{d.title}</strong><div className="small muted">{d.job_family_label} · v{d.version}</div></td>
                  <td>{d.employer.name}</td>
                  <td>{d.stream}</td>
                  <td>{inst(d.institute_ids)}</td>
                  <td>{d.programme_codes.join(", ")}</td>
                  <td>{total}{d.counts.shared ? <span className="small muted"> · {d.counts.shared} shared</span> : null}</td>
                  <td><Pill kind={d.status === "open" ? "good" : d.status === "draft" ? "warn" : ""}>{d.status}</Pill></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
