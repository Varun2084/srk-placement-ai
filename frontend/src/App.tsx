import { useEffect, useState } from "react";
import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { api, clearSession, savedUser, type User } from "./api";
import { useT } from "./i18n";
import { MetaProvider } from "./meta";
import Login from "./pages/Login";
import StudentHome from "./pages/StudentHome";
import StudentDrives from "./pages/StudentDrives";
import Students from "./pages/Students";
import StudentDetail from "./pages/StudentDetail";
import Drives from "./pages/Drives";
import DriveForm from "./pages/DriveForm";
import Queue from "./pages/Queue";
import Employer from "./pages/Employer";
import Reports from "./pages/Reports";
import Audit from "./pages/Audit";

const ROLE_LABEL: Record<string, string> = {
  admin: "Group Admin",
  tpo: "Central TPO",
  coordinator: "Placement Coordinator",
  student: "Student",
  employer: "Employer",
};

export default function App() {
  const [user, setUser] = useState<User | null>(savedUser());
  const { t, lang, setLang } = useT();

  useEffect(() => {
    if (user) api<User>("/api/auth/me").catch(() => setUser(null));
  }, []);

  if (!user) return <Login onLogin={setUser} />;

  const staff = ["admin", "tpo", "coordinator"].includes(user.role);
  const links: [string, string][] =
    user.role === "student"
      ? [["/", t("myProfile")], ["/my-drives", t("drives")]]
      : user.role === "employer"
        ? [["/", "Shared candidates"]]
        : [
            ["/", "Dashboard"],
            ["/drives", "Drives"],
            ["/students", "Students"],
            ...(user.role !== "coordinator" ? ([["/audit", "Audit log"]] as [string, string][]) : []),
          ];

  return (
    <MetaProvider>
      <div className="shell">
        <nav className="side" aria-label="Main">
          <div className="logo">SRK Placement AI</div>
          <div className="sub">Shri Rama Krishna Group, Satna</div>
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end>
              {label}
            </NavLink>
          ))}
          <div className="spacer" />
          {user.role === "student" && (
            <button className="ghost" style={{ color: "#f3e9e4", borderColor: "rgba(255,255,255,.3)", margin: "0 10px 10px" }}
              onClick={() => setLang(lang === "en" ? "hi" : "en")}>
              {lang === "en" ? "हिंदी" : "English"}
            </button>
          )}
          <div className="who">
            {user.name}
            <br />
            <span style={{ opacity: 0.7 }}>{ROLE_LABEL[user.role]}</span>
            <br />
            <a href="#" onClick={(e) => { e.preventDefault(); clearSession(); setUser(null); }} style={{ padding: 0 }}>
              {t("logout")}
            </a>
          </div>
        </nav>
        <main className="main">
          <Routes>
            {user.role === "student" && (
              <>
                <Route path="/" element={<StudentHome />} />
                <Route path="/my-drives" element={<StudentDrives />} />
              </>
            )}
            {user.role === "employer" && <Route path="/" element={<Employer />} />}
            {staff && (
              <>
                <Route path="/" element={<Reports user={user} />} />
                <Route path="/drives" element={<Drives user={user} />} />
                <Route path="/drives/new" element={<DriveForm user={user} />} />
                <Route path="/drives/:id/edit" element={<DriveForm user={user} />} />
                <Route path="/drives/:id" element={<Queue user={user} />} />
                <Route path="/students" element={<Students user={user} />} />
                <Route path="/students/:id" element={<StudentDetail user={user} />} />
                <Route path="/audit" element={<Audit />} />
              </>
            )}
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </main>
      </div>
    </MetaProvider>
  );
}
