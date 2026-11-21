import { useState } from "react";
import { api } from "../api";
import { ErrorBox } from "../ui";

export default function ChangePassword() {
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [again, setAgain] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setError(null); setOk(false);
    if (newPw !== again) return setError("New passwords do not match");
    try {
      await api("/api/auth/change-password", { method: "POST", json: { old_password: oldPw, new_password: newPw } });
      setOk(true); setOldPw(""); setNewPw(""); setAgain("");
    } catch (err: any) { setError(err.message); }
  }

  return (
    <form className="card" style={{ maxWidth: 420 }} onSubmit={save}>
      <h1>Change password</h1>
      <div className="field"><label htmlFor="o">Current password</label><input id="o" type="password" autoComplete="current-password" value={oldPw} onChange={(e) => setOldPw(e.target.value)} required /></div>
      <div className="field"><label htmlFor="n">New password (8+ characters)</label><input id="n" type="password" autoComplete="new-password" minLength={8} value={newPw} onChange={(e) => setNewPw(e.target.value)} required /></div>
      <div className="field"><label htmlFor="a">New password again</label><input id="a" type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} required /></div>
      <ErrorBox error={error} />
      {ok && <div className="ok">Password changed.</div>}
      <button className="primary">Save</button>
    </form>
  );
}
