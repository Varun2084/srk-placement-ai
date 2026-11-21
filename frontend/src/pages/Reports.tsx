import { useEffect, useState } from "react";
import { api, download, type User } from "../api";
import { Bar, ErrorBox, Pill } from "../ui";

export default function Reports({ user }: { user: User }) {
  const [r, setR] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api("/api/reports/summary").then(setR).catch((e) => setError(e.message)); }, []);
  if (!r) return <ErrorBox error={error} />;

  const tot = r.programmes.reduce((a: any, p: any) => ({
    students: a.students + p.students, consented: a.consented + p.consented,
    resume_parsed: a.resume_parsed + p.resume_parsed, verified: a.verified + p.verified,
  }), { students: 0, consented: 0, resume_parsed: 0, verified: 0 });
  const maxFunnel = Math.max(1, r.funnel[0]?.count ?? 1);

  return (
    <>
      <div className="topline">
        <div>
          <h1>Placement dashboard</h1>
          <p className="muted" style={{ margin: 0 }}>{user.role === "coordinator" ? "Your institute" : "SRKCESM and SRKCP combined"} · synthetic demo data</p>
        </div>
        <button onClick={() => download("/api/reports/placements.csv", "placements.csv")}>Export CSV (NAAC/NIRF)</button>
      </div>
      <ErrorBox error={error} />
      <div className="kpis">
        <div className="kpi"><div className="v">{tot.students}</div><div className="l">Students</div></div>
        <div className="kpi"><div className="v">{tot.consented}</div><div className="l">Gave privacy consent</div></div>
        <div className="kpi"><div className="v">{tot.resume_parsed}</div><div className="l">Resumes parsed</div></div>
        <div className="kpi"><div className="v">{tot.verified}</div><div className="l">Academics verified</div></div>
      </div>
      <div className="grid2">
        <div className="card">
          <h2>Drive funnel</h2>
          {r.funnel.map((f: any) => (
            <div key={f.stage} className="row" style={{ marginBottom: 8 }}>
              <span style={{ width: 100 }}>{f.stage}</span>
              <span style={{ flex: 1 }}><Bar value={(f.count / maxFunnel) * 100} /></span>
              <span className="score" style={{ width: 36, textAlign: "right" }}>{f.count}</span>
            </div>
          ))}
          <p className="small muted">Human reviews: {r.reviews.total} · overrides of AI suggestion: {r.reviews.overrides}</p>
        </div>
        <div className="card">
          <h2>Fairness monitor</h2>
          <p className="small muted">{r.fairness.note}</p>
          {r.fairness.four_fifths_flag && <div className="notice">One group's shortlist rate is below 80% of the highest. Review criteria and decisions.</div>}
          <table>
            <thead><tr><th>Group</th><th>Reviewed</th><th>Shortlisted</th><th>Rate</th></tr></thead>
            <tbody>
              {r.fairness.groups.length === 0 && <tr><td colSpan={4} className="muted">No reviewed applications yet.</td></tr>}
              {r.fairness.groups.map((g: any) => (
                <tr key={g.group}><td>{g.group}</td><td>{g.reviewed}</td><td>{g.shortlisted}</td><td>{g.rate != null ? `${Math.round(g.rate * 100)}%` : "—"}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="card">
        <h2>Readiness pipeline by programme</h2>
        <table>
          <thead><tr><th>Institute · programme</th><th>Students</th><th>Consent</th><th>Resume parsed</th><th>Verified</th><th>Offers</th></tr></thead>
          <tbody>
            {r.programmes.map((p: any) => (
              <tr key={p.group}>
                <td>{p.group}</td><td>{p.students}</td><td>{p.consented}</td><td>{p.resume_parsed}</td>
                <td>{p.verified} {p.verified < p.students && <Pill kind="warn">{p.students - p.verified} pending</Pill>}</td>
                <td>{p.offered}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
