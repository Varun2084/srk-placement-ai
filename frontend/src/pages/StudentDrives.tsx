import { useEffect, useState } from "react";
import { api } from "../api";
import { useT } from "../i18n";
import { useMeta } from "../meta";
import { ErrorBox, Pill, StatusPill } from "../ui";

export default function StudentDrives() {
  const { t } = useT();
  const meta = useMeta();
  const [drives, setDrives] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = () => api<any[]>("/api/drives").then(setDrives).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function act(path: string) {
    setError(null);
    try { await api(path, { method: "POST" }); load(); } catch (e: any) { setError(e.message); }
  }

  return (
    <>
      <h1>{t("drives")}</h1>
      <p className="muted">Open drives for your programme. Applying does not share your profile; you choose separately for each employer.</p>
      <ErrorBox error={error} />
      {drives.length === 0 && <div className="card muted">No open drives for your programme right now.</div>}
      {drives.map((d) => (
        <div className="card" key={d.id}>
          <div className="topline" style={{ marginBottom: 8 }}>
            <div>
              <h2 style={{ marginBottom: 2 }}>{d.title}</h2>
              <div className="muted">{d.employer.name} · {d.job_family_label}</div>
            </div>
            {d.my_application ? <StatusPill status={d.my_application} /> : <button className="primary" onClick={() => act(`/api/drives/${d.id}/apply`)}>{t("apply")}</button>}
          </div>
          <p>{d.description}</p>
          <div className="row small">
            {d.min_cgpa != null && <Pill>CGPA ≥ {d.min_cgpa}</Pill>}
            {d.min_aggregate_pct != null && <Pill>Aggregate ≥ {d.min_aggregate_pct}%</Pill>}
            {d.max_backlogs != null && <Pill>Backlogs ≤ {d.max_backlogs}</Pill>}
            {d.required_skills.map((s: string) => <Pill kind="info" key={s}>{meta?.skills[s] ?? s}</Pill>)}
          </div>
          <label className="row" style={{ marginTop: 12, color: "var(--ink)" }}>
            <input type="checkbox" style={{ width: "auto" }} checked={d.my_share_consent}
              onChange={(e) => act(`/api/drives/${d.id}/share-consent?granted=${e.target.checked}`)} />
            {t("shareWith")} ({d.employer.name})
          </label>
        </div>
      ))}
    </>
  );
}
