import { Fragment, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type User } from "../api";
import { useMeta } from "../meta";
import { Bar, ErrorBox, Evidence, GatePill, Pill, StatusPill } from "../ui";

const DECISIONS: [string, string][] = [["shortlisted", "Shortlist"], ["on_hold", "Hold"], ["not_selected", "Not selected"]];

export default function Queue({ user }: { user: User }) {
  const { id } = useParams();
  const meta = useMeta();
  const [q, setQ] = useState<any>(null);
  const [open, setOpen] = useState<number | null>(null);
  const [modal, setModal] = useState<{ app: any; decision: string } | null>(null);
  const [reason, setReason] = useState("");
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => api(`/api/drives/${id}/queue`).then(setQ).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [id]);

  async function post(path: string, label: string) {
    setBusy(true); setError(null); setMsg(null);
    try {
      const r: any = await api(path, { method: "POST" });
      setMsg(label + (r.added !== undefined ? `: ${r.added} added` : r.shared !== undefined ? `: ${r.shared} shared, ${r.awaiting_student_consent} awaiting student consent` : ""));
      await load();
    } catch (e: any) { setError(e.message); } finally { setBusy(false); }
  }

  async function decide() {
    if (!modal) return;
    try {
      const r: any = await api(`/api/applications/${modal.app.application_id}/review`, { method: "POST", json: { decision: modal.decision, reason } });
      setMsg(r.override ? "Saved as an override of the AI suggestion (reason recorded)." : "Decision saved.");
      setModal(null); setReason(""); load();
    } catch (e: any) { setError(e.message); }
  }

  if (!q) return <ErrorBox error={error} />;
  const d = q.drive;
  const items = q.items.filter((i: any) =>
    filter === "all" ? true : filter === "undecided" ? i.status === "applied" : i.result?.gate_status === filter);
  const isTpo = user.role === "tpo" || user.role === "admin";
  const shortlisted = q.items.filter((i: any) => i.status === "shortlisted").length;

  return (
    <>
      <div className="topline">
        <div>
          <h1>{d.title}</h1>
          <div className="muted">{d.employer.name} · {d.job_family_label} · drive v{d.version}</div>
          <div className="row small" style={{ marginTop: 8 }}>
            {d.min_cgpa != null && <Pill>CGPA ≥ {d.min_cgpa}</Pill>}
            {d.min_aggregate_pct != null && <Pill>Aggregate ≥ {d.min_aggregate_pct}%</Pill>}
            {d.max_backlogs != null && <Pill>Backlogs ≤ {d.max_backlogs}</Pill>}
            {d.branches.length > 0 && <Pill>{d.branches.join(", ")}</Pill>}
            {d.required_skills.map((s: string) => <Pill kind="info" key={s}>{meta?.skills[s] ?? s}</Pill>)}
            {d.preferred_skills.map((s: string) => <Pill key={s}>{meta?.skills[s] ?? s} (pref)</Pill>)}
          </div>
        </div>
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <Link to={`/drives/${id}/edit`}><button>Edit</button></Link>
          {Object.keys(d.weights).length > 0 && !d.weights_approved && isTpo &&
            <button onClick={() => post(`/api/drives/${id}/approve-weights`, "Weights approved")}>Approve weights</button>}
          <button disabled={busy} onClick={() => post(`/api/drives/${id}/enrol-eligible`, "Students enrolled")}>Enrol programme students</button>
          <button className="primary" disabled={busy} onClick={() => post(`/api/drives/${id}/match`, "Matching complete")}>Run matching</button>
          {isTpo && <button className="good" disabled={busy || shortlisted === 0} onClick={() => post(`/api/drives/${id}/approve-shortlist`, "Shortlist approved")}>
            Approve shortlist ({shortlisted})</button>}
        </div>
      </div>
      <div className="notice">{q.notice} {q.run && <span>Last run #{q.run.id}: {q.run.rubric}, {q.run.parser}, {q.run.taxonomy}, drive v{q.run.drive_version}.</span>}</div>
      <ErrorBox error={error} />
      {msg && <div className="ok">{msg}</div>}
      <div className="row" style={{ marginBottom: 10 }}>
        {[["all", "All"], ["undecided", "Not yet reviewed"], ["pass", "Eligible"], ["needs_verification", "Verify data"], ["fail", "Rule not met"]].map(([k, l]) => (
          <button key={k} className={filter === k ? "primary" : ""} onClick={() => setFilter(k)}>{l}</button>
        ))}
        <span className="muted small">{items.length} of {q.items.length}</span>
      </div>
      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead><tr><th>#</th><th>Student</th><th>Eligibility</th><th style={{ width: 170 }}>Evidence score</th><th>Confidence</th><th>Status</th><th>Decide</th></tr></thead>
          <tbody>
            {items.map((i: any) => (
              <Fragment key={i.application_id}>
                <tr className="clickable" onClick={() => setOpen(open === i.application_id ? null : i.application_id)} aria-expanded={open === i.application_id}>
                  <td>{i.rank ?? "—"}</td>
                  <td><strong>{i.student.name}</strong><div className="small muted">{i.student.institute} · {i.student.programme} {i.student.branch} · {i.student.roll_no}</div></td>
                  <td><GatePill status={i.result?.gate_status} /></td>
                  <td>{i.result ? <div className="row"><span style={{ flex: 1 }}><Bar value={i.result.score} /></span><span className="score">{i.result.score}</span></div> : <span className="muted">run matching</span>}</td>
                  <td>{i.result && <Pill kind={i.result.confidence === "high" ? "good" : i.result.confidence === "medium" ? "warn" : "bad"}>{i.result.confidence}</Pill>}</td>
                  <td><StatusPill status={i.status} />{i.share_consent && <div className="small muted">consented to share</div>}</td>
                  <td onClick={(e) => e.stopPropagation()} className="row" style={{ gap: 4 }}>
                    {DECISIONS.map(([k, l]) => <button key={k} className="small" style={{ padding: "3px 8px" }} onClick={() => setModal({ app: i, decision: k })}>{l}</button>)}
                  </td>
                </tr>
                {open === i.application_id && i.result && (
                  <tr className="expand"><td colSpan={7}>
                    <p>{i.result.explanation}</p>
                    <div className="grid2">
                      <div>
                        <h3>Criteria and evidence</h3>
                        {i.result.criteria.map((c: any) => <Evidence key={c.kind + c.skill} c={c} />)}
                      </div>
                      <div>
                        <h3>Eligibility gates</h3>
                        {i.result.gates.map((g: any) => (
                          <div key={g.gate} className="row small" style={{ marginBottom: 4 }}>
                            <Pill kind={g.status === "pass" ? "good" : g.status === "fail" ? "bad" : "warn"}>{g.status}</Pill> {g.detail}
                          </div>
                        ))}
                        <h3 style={{ marginTop: 12 }}>Score breakdown</h3>
                        <div className="small">
                          Required skills {i.result.breakdown.parts.required} · Preferred {i.result.breakdown.parts.preferred} · Project/JD relevance {i.result.breakdown.parts.context}
                          <br />Weights {JSON.stringify(i.result.breakdown.weights)} · data completeness {Math.round(i.result.completeness * 100)}%
                        </div>
                        {i.result.warnings.length > 0 && <div className="notice" style={{ marginTop: 10 }}>{i.result.warnings.join("; ")}</div>}
                        {i.reviews.length > 0 && (
                          <>
                            <h3 style={{ marginTop: 12 }}>Decision history</h3>
                            {i.reviews.map((r: any, k: number) => (
                              <div key={k} className="small">{new Date(r.at).toLocaleString()} · {r.by}: <strong>{r.decision}</strong>{r.override && " (override)"} — {r.reason}</div>
                            ))}
                          </>
                        )}
                        <p className="small"><Link to={`/students/${i.student.id}`}>Open student profile →</Link></p>
                      </div>
                    </div>
                  </td></tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {modal && (
        <div className="modal-back" role="dialog" aria-modal="true" aria-labelledby="dtitle">
          <div className="modal">
            <h2 id="dtitle">{DECISIONS.find(([k]) => k === modal.decision)?.[1]}: {modal.app.student.name}</h2>
            <p className="small muted">AI score {modal.app.result?.score ?? "—"}, eligibility {modal.app.result?.gate_status ?? "not matched"}. Your reason is stored in the audit log.</p>
            <label htmlFor="reason">Reason (required)</label>
            <textarea id="reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} autoFocus />
            <div className="row" style={{ marginTop: 12, justifyContent: "flex-end" }}>
              <button onClick={() => { setModal(null); setReason(""); }}>Cancel</button>
              <button className="primary" disabled={reason.trim().length < 5} onClick={decide}>Save decision</button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
