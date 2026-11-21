import type { ReactNode } from "react";

export function Pill({ kind = "", children }: { kind?: string; children: ReactNode }) {
  return <span className={`pill ${kind}`}>{children}</span>;
}

const GATE: Record<string, [string, string]> = {
  pass: ["good", "Eligible"],
  needs_verification: ["warn", "Verify data"],
  fail: ["bad", "Rule not met"],
};
export function GatePill({ status }: { status?: string }) {
  if (!status) return <Pill>Not matched</Pill>;
  const [k, l] = GATE[status] ?? ["", status];
  return <Pill kind={k}>{l}</Pill>;
}

const STATUS: Record<string, string> = {
  applied: "",
  shortlisted: "info",
  on_hold: "warn",
  not_selected: "bad",
  approved: "brand",
  shared: "good",
  interview: "good",
  offered: "good",
};
export function StatusPill({ status }: { status: string }) {
  return <Pill kind={STATUS[status] ?? ""}>{status.replace("_", " ")}</Pill>;
}

export function Bar({ value }: { value: number }) {
  return (
    <div className="bar" role="img" aria-label={`${Math.round(value)} out of 100`}>
      <span style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
    </div>
  );
}

export function ErrorBox({ error }: { error: string | null }) {
  return error ? <div className="error" role="alert">{error}</div> : null;
}

export function Evidence({ c }: { c: any }) {
  const label =
    c.status === "evidenced"
      ? `found in ${c.section}`
      : c.status === "related"
        ? `related: ${c.related_skill} (${c.section})`
        : "not evidenced in resume";
  return (
    <div className={`evidence ${c.status}`}>
      <strong>{c.label}</strong> <span className="muted small">· {c.kind} · {label}</span>
      {c.snippet && <div className="snippet">“{c.snippet}”</div>}
    </div>
  );
}
