import {useMemo, useState} from "react";
import {createApi} from "./api.js";
import {Login} from "./views/Login.jsx";
import {Dashboard} from "./views/Dashboard.jsx";
import {BatchView} from "./views/BatchView.jsx";
import {BellijstView} from "./views/BellijstView.jsx";
import {DetailView} from "./views/DetailView.jsx";
import {ChatSessiesView} from "./views/ChatSessiesView.jsx";
import {ChatTemplatesView} from "./views/ChatTemplatesView.jsx";
import {JaarverslagenView} from "./views/JaarverslagenView.jsx";
import {JaarverslagChatView} from "./views/JaarverslagChatView.jsx";
import {ChatForm} from "./views/ChatForm.jsx";

export default function App() {
  // Publieke chat-route — afhandelen vóór auth-flow
  const chatToken = new URLSearchParams(window.location.search).get("chat");
  if (chatToken) return <ChatForm token={chatToken} />;

  const [token, setToken] = useState(() => localStorage.getItem("token") || "");
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  });
  const [route, setRoute] = useState({name: "dashboard"});

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
    setRoute({name: "dashboard"});
  }

  if (!token) return <Login api={api} onLogin={login} />;

  if (route.name === "batch") {
    return (
      <BatchView
        api={api}
        user={user}
        onLogout={logout}
        batchId={route.batchId}
        openDashboard={() => setRoute({name: "dashboard"})}
        openCompany={(batchId, companyId) => setRoute({name: "detail", batchId, companyId})}
        openBellijst={(batchId) => setRoute({name: "bellijst", batchId})}
        openChatSessies={(batchId) => setRoute({name: "chat-sessies", batchId})}
      />
    );
  }

  if (route.name === "bellijst") {
    return (
      <BellijstView
        api={api}
        user={user}
        onLogout={logout}
        batchId={route.batchId}
        openBatch={(batchId) => setRoute({name: "batch", batchId})}
      />
    );
  }

  if (route.name === "chat-sessies") {
    return (
      <ChatSessiesView
        api={api}
        user={user}
        onLogout={logout}
        batchId={route.batchId}
        openBatch={(batchId) => setRoute({name: "batch", batchId})}
      />
    );
  }

  if (route.name === "chat-templates") {
    return (
      <ChatTemplatesView
        api={api}
        user={user}
        onLogout={logout}
        openDashboard={() => setRoute({name: "dashboard"})}
      />
    );
  }

  if (route.name === "jaarverslagen") {
    return (
      <JaarverslagenView
        api={api}
        user={user}
        onLogout={logout}
        openDashboard={() => setRoute({name: "dashboard"})}
        openChat={(uploadId) => setRoute({name: "jaarverslag-chat", uploadId})}
      />
    );
  }

  if (route.name === "jaarverslag-chat") {
    return (
      <JaarverslagChatView
        api={api}
        user={user}
        onLogout={logout}
        uploadId={route.uploadId}
        openJaarverslagen={() => setRoute({name: "jaarverslagen"})}
      />
    );
  }

  if (route.name === "detail") {
    return (
      <DetailView
        api={api}
        user={user}
        onLogout={logout}
        batchId={route.batchId}
        companyId={route.companyId}
        openBatch={(batchId) => setRoute({name: "batch", batchId})}
      />
    );
  }

  return (
    <Dashboard
      api={api}
      user={user}
      onLogout={logout}
      openBatch={(batchId) => setRoute({name: "batch", batchId})}
      openChatTemplates={() => setRoute({name: "chat-templates"})}
      openJaarverslagen={() => setRoute({name: "jaarverslagen"})}
    />
  );
}
