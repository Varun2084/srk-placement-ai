import { useEffect, useState } from "react";
import { api, download, type User } from "../api";
import { useMeta } from "../meta";
import { ErrorBox, Pill } from "../ui";

function saveText(text: string, filename: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/csv" }));
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

export default function Accounts({ user }: { user: User }) {
  const meta = useMeta();
  const group = user.role === "admin" || user.role === "tpo";
  const [users, setUsers] = useState<any[]>([]);
  const [form, setForm] = useState({ email: "", name: "", role: "coordinator", institute_id: "", employer_name: "" });
  const [created, setCreated] = useState<string | null>(null);
  const [imp, setImp] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => group && api<any[]>("/api/admin/users").then(setUsers).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  async function createUser() {
    setError(null); setCreated(null);
    try {
      const r: any = await api("/api/admin/users", {
        method: "POST",
        json: { ...form, institute_id: form.institute_id ? Number(form.institute_id) : null, employer_name: form.employer_name || null },
      });
      setCreated(`${r.email} — temporary password: ${r.temporary_password} (share it privately; ask them to change it)`);
      setForm({ ...form, email: "", name: "" });
      load();
    } catch (e: any) { setError(e.message); }
  }

  async function importCsv(file: File) {
    setError(null); setImp(null);
    const fd = new FormData();
    fd.append("file", file);
    try { setImp(await api("/api/admin/students/import", { method: "POST", body: fd })); } catch (e: any) { setError(e.message); }
  }

  return (
    <>
      <h1>Accounts</h1>
      <ErrorBox error={error} />
      <div className="card">
        <h2>Import students from CSV</h2>
        <p className="small muted">
          One row per student, from the college record. CGPA / aggregate / backlogs in the file are marked as verified.
          {user.role === "coordinator" && " You can import only your own institute's students."}
        </p>
        <div className="row">
          <button onClick={() => download("/api/admin/students/template.csv", "students_template.csv")}>Download template</button>
          <input type="file" accept=".csv" style={{ width: 320 }} aria-label="Students CSV" onChange={(e) => e.target.files?.[0] && importCsv(e.target.files[0])} />
        </div>
        {imp && (
          <div className="ok">
            {imp.created} created, {imp.skipped} already existed.{" "}
            <a href="#" onClick={(e) => { e.preventDefault(); saveText(imp.result_csv, "student_logins.csv"); }}>Download login passwords (CSV)</a>
            {" "}— keep this file private and delete it after distributing.
          </div>
        )}
      </div>

      {group && (
        <>
          <div className="card">
            <h2>Add staff or employer account</h2>
            <div className="grid3">
              <div className="field"><label>Name</label><input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
              <div className="field"><label>Email</label><input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
              <div className="field"><label>Role</label>
                <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  <option value="coordinator">Placement coordinator</option>
                  <option value="tpo">TPO</option>
                  <option value="employer">Employer recruiter</option>
                  {user.role === "admin" && <option value="admin">Admin</option>}
                </select>
              </div>
              {form.role === "coordinator" && (
                <div className="field"><label>Institute</label>
                  <select value={form.institute_id} onChange={(e) => setForm({ ...form, institute_id: e.target.value })}>
                    <option value="">Choose…</option>
                    {meta?.institutes.map((i) => <option key={i.id} value={i.id}>{i.code}</option>)}
                  </select>
                </div>
              )}
              {form.role === "employer" && (
                <div className="field"><label>Company</label><input value={form.employer_name} onChange={(e) => setForm({ ...form, employer_name: e.target.value })} /></div>
              )}
            </div>
            <button className="primary" onClick={createUser}>Create account</button>
            {created && <div className="ok">{created}</div>}
          </div>
          <div className="card">
            <h2>Staff and employer accounts</h2>
            <table>
              <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Scope</th></tr></thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.name}</td><td>{u.email}</td><td><Pill>{u.role}</Pill></td>
                    <td className="small muted">{u.employer ?? meta?.institutes.find((i) => i.id === u.institute_id)?.code ?? "All institutes"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
