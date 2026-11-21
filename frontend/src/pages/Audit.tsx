import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorBox } from "../ui";

export default function Audit() {
  const [rows, setRows] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api<any[]>("/api/audit?limit=500").then(setRows).catch((e) => setError(e.message)); }, []);
  const shown = rows.filter((r) => !q || JSON.stringify(r).toLowerCase().includes(q.toLowerCase()));
  return (
    <>
      <h1>Audit log</h1>
      <p className="muted">Every login, view, upload, match run, decision, approval and export. Read-only.</p>
      <ErrorBox error={error} />
      <input placeholder="Filter (e.g. application.review, override, a name)" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 420, marginBottom: 12 }} />
      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Object</th><th>Detail</th></tr></thead>
          <tbody>
            {shown.map((r) => (
              <tr key={r.id}>
                <td className="small">{new Date(r.at).toLocaleString()}</td>
                <td>{r.actor}<div className="small muted">{r.role}</div></td>
                <td><code>{r.action}</code></td>
                <td className="small">{r.object}</td>
                <td className="small muted" style={{ maxWidth: 420, overflowWrap: "anywhere" }}>{JSON.stringify(r.detail).slice(0, 220)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
