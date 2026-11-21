import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";

export interface Meta {
  institutes: { id: number; code: string; name: string }[];
  programmes: { id: number; institute_id: number; code: string; name: string; stream: string; branches: string[] }[];
  skills: Record<string, string>;
  job_families: Record<string, Record<string, { label: string; core: string[]; optional: string[] }>>;
}

const Ctx = createContext<Meta | null>(null);

export function MetaProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  useEffect(() => {
    api<Meta>("/api/meta").then(setMeta).catch(() => {});
  }, []);
  return <Ctx.Provider value={meta}>{children}</Ctx.Provider>;
}

export const useMeta = () => useContext(Ctx);
