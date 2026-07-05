import {useState} from "react";
import {ShieldCheck} from "lucide-react";
import {IconButton} from "../components/IconButton.jsx";

export function Login({api, onLogin}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api.login(email, password);
      onLogin(result.access_token, result.user);
    } catch (err) {
      setError(err.message || "Inloggen mislukt");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5] px-4">
      <form onSubmit={submit} className="w-full max-w-sm rounded-lg border border-line bg-white p-6 shadow-sm">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-[#C8102E] text-white">
            <ShieldCheck size={22} />
          </div>
          <div>
            <h1 className="text-xl font-semibold">Vestigingsregister</h1>
            <p className="text-sm text-slate-500">Etil Research Group · Provincie Limburg</p>
          </div>
        </div>
        <label className="mb-2 block text-sm font-medium" htmlFor="email">E-mail</label>
        <input
          id="email"
          className="focus-ring mb-4 h-11 w-full rounded-md border border-line px-3"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          autoComplete="username"
        />
        <label className="mb-2 block text-sm font-medium" htmlFor="password">Wachtwoord</label>
        <input
          id="password"
          type="password"
          className="focus-ring mb-4 h-11 w-full rounded-md border border-line px-3"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          autoComplete="current-password"
        />
        {error ? <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</div> : null}
        <IconButton icon={ShieldCheck} variant="primary" className="w-full justify-center" disabled={busy}>
          {busy ? "Bezig..." : "Inloggen"}
        </IconButton>
      </form>
    </main>
  );
}
