import {useState} from "react";
import {ShieldCheck} from "lucide-react";

const VELD =
  "focus-ring-licht h-[46px] w-full rounded-[10px] border border-seasalt/20 " +
  "bg-white/5 px-3.5 text-[15px] text-seasalt placeholder:text-seasalt/35";

export function Login({api, onLogin, melding = ""}) {
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
    <main
      className="relative flex min-h-screen items-center justify-center bg-night bg-cover bg-center px-6 lg:justify-start lg:px-32"
      style={{backgroundImage: "url(/login-hero.jpg)"}}
    >
      {/* De foto is licht aan de rechterkant; zonder deze laag verdwijnt het
          paneel erin zodra de browser hem anders uitsnijdt. */}
      <div
        aria-hidden="true"
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 70% 80% at 74% 52%, rgba(18,18,18,0.30) 0%," +
            " rgba(18,18,18,0.74) 52%, rgba(18,18,18,0.92) 100%)",
        }}
      />

      <div className="relative flex w-full max-w-[400px] flex-col gap-7">
        <h1 className="text-center text-[30px] font-bold tracking-tight text-seasalt">
          Bronnenwerkbank
        </h1>

        <form
          onSubmit={submit}
          className="flex flex-col gap-4 rounded-2xl border border-seasalt/15 p-[30px]"
          style={{
            background: "rgba(18,18,18,0.55)",
            backdropFilter: "blur(18px) saturate(140%)",
            boxShadow: "0 24px 60px rgba(0,0,0,0.45)",
          }}
        >
          {/* Waarom je hier weer bent. Zonder deze regel vlieg je er na twaalf
              uur uit zonder uitleg, en dan lijkt het alsof er iets stuk is. */}
          {melding ? (
            <p className="rounded-[10px] border border-spectrum-orange/40 bg-spectrum-orange/10 px-3 py-2.5 text-[13px] font-light leading-normal text-seasalt/90">
              {melding}
            </p>
          ) : null}

          <div className="flex flex-col gap-2">
            <label className="text-[13px] font-medium text-seasalt/70" htmlFor="email">
              E-mail
            </label>
            <input
              id="email"
              className={VELD}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="username"
            />
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-[13px] font-medium text-seasalt/70" htmlFor="password">
              Wachtwoord
            </label>
            <input
              id="password"
              type="password"
              className={VELD}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </div>

          {error ? (
            <div
              role="alert"
              className="rounded-[10px] border border-spectrum-red/45 bg-spectrum-red/10 px-3 py-2.5 text-[13px] leading-normal text-foutlicht"
            >
              {error}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={busy}
            className="data-verloop focus-ring-licht mt-1 inline-flex h-12 items-center justify-center gap-2.5 rounded-[10px] text-[15px] font-bold text-night transition disabled:opacity-60"
            style={{boxShadow: "0 8px 24px rgba(255,80,0,0.28)"}}
          >
            <ShieldCheck size={17} />
            {busy ? "Bezig..." : "Inloggen"}
          </button>
        </form>

        <div className="flex justify-center">
          <img
            src="/etil-logo-seasalt.png"
            alt="Etil — connecting insights to impact."
            className="h-auto w-[168px] opacity-85"
          />
        </div>
      </div>
    </main>
  );
}
