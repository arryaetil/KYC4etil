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
  // Waarom je bent uitgelogd. Zonder dit vloog je er na twaalf uur uit op
  // het inlogscherm, zonder enige uitleg — en dan denk je dat er iets stuk
  // is in plaats van dat je sessie gewoon verlopen was.
  const [uitlogreden, setUitlogreden] = useState("");

  const api = useMemo(
    () => createApi(token, () => logout(
      "Je sessie is verlopen. Log opnieuw in; je werk is bewaard.",
    )),
    [token],
  );

  function login(nextToken, nextUser) {
    setUitlogreden("");
    localStorage.setItem("token", nextToken);
    localStorage.setItem("user", JSON.stringify(nextUser));
    setToken(nextToken);
    setUser(nextUser);
  }

  function logout(reden = "") {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setToken("");
    setUser(null);
    setModule("onderzoek");
    setUitlogreden(reden);
  }

  if (!token) return <Login api={api} onLogin={login} melding={uitlogreden} />;

  return (
    <AppShell user={user} module={module} onModule={setModule} onLogout={() => logout()}>
      {module === "instellingen"
        ? <InstellingenView api={api} user={user} />
        : module === "onderzoek"
          ? <OnderzoekView api={api} />
          : <MonitoringView api={api} />}
    </AppShell>
  );
}
