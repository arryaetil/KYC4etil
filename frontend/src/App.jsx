import {useMemo, useState} from "react";
import {createApi} from "./api.js";
import {Login} from "./views/Login.jsx";
import {ChatForm} from "./views/ChatForm.jsx";
import {AppShell} from "./components/AppShell.jsx";
import {OnderzoekView} from "./views/OnderzoekView.jsx";
import {MonitoringView} from "./views/MonitoringView.jsx";

export default function App() {
  // Publieke chat-route — afhandelen vóór de auth-flow, want deze link wordt
  // buiten de applicatie om gedeeld.
  const chatToken = new URLSearchParams(window.location.search).get("chat");
  if (chatToken) return <ChatForm token={chatToken} />;

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
      {module === "onderzoek"
        ? <OnderzoekView api={api} />
        : <MonitoringView api={api} />}
    </AppShell>
  );
}
