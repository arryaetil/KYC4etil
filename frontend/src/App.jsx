import {useMemo, useState} from "react";
import {createApi} from "./api.js";
import {Login} from "./views/Login.jsx";
import {AppShell} from "./components/AppShell.jsx";
import {OnderzoekView} from "./views/OnderzoekView.jsx";
import {InstellingenView} from "./views/InstellingenView.jsx";
import {MonitoringView} from "./views/MonitoringView.jsx";

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem("token") || "");
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  });
  const [module, setModule] = useState("onderzoek");

  const api = useMemo(() => createApi(token, () => logout()), [token]);

  function login(nextToken, nextUser) {
    localStorage.setItem("token", nextToken);
    localStorage.setItem("user", JSON.stringify(nextUser));
    setToken(nextToken);
    setUser(nextUser);
  }

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setToken("");
    setUser(null);
    setModule("onderzoek");
  }

  if (!token) return <Login api={api} onLogin={login} />;

  return (
    <AppShell user={user} module={module} onModule={setModule} onLogout={logout}>
      {module === "instellingen"
        ? <InstellingenView api={api} user={user} />
        : module === "onderzoek"
          ? <OnderzoekView api={api} />
          : <MonitoringView api={api} />}
    </AppShell>
  );
}
