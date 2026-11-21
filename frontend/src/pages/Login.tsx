import { useState } from "react";
import { api, saveSession, type User } from "../api";
import { ErrorBox } from "../ui";

const DEMO = [
  ["TPO", "tpo@srk.demo"],
  ["Coordinator SRKCESM", "coord.esm@srk.demo"],
  ["Coordinator SRKCP", "coord.cp@srk.demo"],
  ["Student", "student001@srk.demo"],
  ["Employer (IT)", "hr@vindhyainfotech.demo"],
  ["Admin", "admin@srk.demo"],
];

export default function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e?: React.FormEvent, em = email, pw = password) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ token: string; user: User }>("/api/auth/login", { method: "POST", json: { email: em, password: pw } });
      saveSession(r.token, r.user);
      onLogin(r.user);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <form className="box" onSubmit={submit}>
        <h1>SRK Placement AI</h1>
        <p className="muted" style={{ marginTop: 0 }}>Shri Rama Krishna Group, Satna · SRKCESM &amp; SRKCP</p>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="pw">Password</label>
          <input id="pw" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        <ErrorBox error={error} />
        <button className="primary" disabled={busy} style={{ width: "100%" }}>Log in</button>
        <div className="demo-accounts">
          Demo accounts (password <code>Srk@2026</code>, synthetic data only):
          <div>
            {DEMO.map(([label, em]) => (
              <button type="button" key={em} onClick={() => { setEmail(em); setPassword("Srk@2026"); submit(undefined, em, "Srk@2026"); }}>
                {label}
              </button>
            ))}
          </div>
        </div>
      </form>
    </div>
  );
}
