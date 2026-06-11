import {useEffect, useMemo, useRef, useState} from "react";
import {
  AlertTriangle,
  Check,
  Download,
  FileDown,
  FileUp,
  ListChecks,
  LogOut,
  Phone,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  Square,
  X,
} from "lucide-react";
import {createApi} from "./api.js";

const LABELS = {
  hoog: {text: "Groen", dot: "bg-emerald-500", bg: "bg-emerald-50", textColor: "text-emerald-800"},
  middel: {text: "Geel", dot: "bg-amber-500", bg: "bg-amber-50", textColor: "text-amber-800"},
  laag: {text: "Rood", dot: "bg-red-500", bg: "bg-red-50", textColor: "text-red-800"},
};

const STRATEGIE_LABELS = {
  auto: "Auto",
  gerichte_chat: "Gerichte chat",
  volledige_chat_of_bellijst: "Volledige chat of bellijst",
  bellijst: "Bellijst",
};

function pct(value) {
  if (!value) return 0;
  return Math.max(0, Math.min(100, Math.round(value * 100)));
}

function classNames(...items) {
  return items.filter(Boolean).join(" ");
}

function IconButton({children, icon: Icon, variant = "default", ...props}) {
  const styles = {
    default: "border-line bg-white text-ink hover:bg-panel",
    primary: "border-etil bg-etil text-white hover:bg-teal-800",
    danger: "border-red-600 bg-red-600 text-white hover:bg-red-700",
    quiet: "border-transparent bg-transparent text-slate-600 hover:bg-panel",
  };
  return (
    <button
      {...props}
      className={classNames(
        "focus-ring inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm font-medium transition",
        styles[variant],
        props.className,
      )}
    >
      {Icon ? <Icon size={17} /> : null}
      {children}
    </button>
  );
}

function LabelBadge({label}) {
  const cfg = LABELS[label] || LABELS.laag;
  return (
    <span className={classNames("inline-flex items-center gap-2 rounded-md px-2 py-1 text-xs font-semibold", cfg.bg, cfg.textColor)}>
      <span className={classNames("h-2 w-2 rounded-full", cfg.dot)} />
      {cfg.text}
    </span>
  );
}

function StatusPill({status}) {
  const label = {
    pending: "Open",
    approved: "Goedgekeurd",
    corrected: "Gecorrigeerd",
    to_chat: "Chat",
    to_call: "Bellijst",
    running: "Draait",
    done: "Klaar",
    error: "Fout",
  }[status] || status || "Onbekend";
  return <span className="rounded-md border border-line bg-white px-2 py-1 text-xs font-medium text-slate-700">{label}</span>;
}

function Login({api, onLogin}) {
  const [email, setEmail] = useState("armina@etil.nl");
  const [password, setPassword] = useState("ArminaDemo2026!");
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
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-etil text-white">
            <ShieldCheck size={22} />
          </div>
          <div>
            <h1 className="text-xl font-semibold">Vestigingsregister</h1>
            <p className="text-sm text-slate-500">Reviewomgeving</p>
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

function Shell({user, onLogout, children, title, actions}) {
  return (
    <div className="min-h-screen bg-[#eef2f5]">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3">
          <div>
            <div className="text-sm font-semibold text-etil">Vestigingsregister AI</div>
            <h1 className="text-xl font-semibold">{title}</h1>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right text-sm sm:block">
              <div className="font-medium">{user?.naam}</div>
              <div className="text-slate-500">{user?.rol}</div>
            </div>
            <IconButton icon={LogOut} variant="quiet" onClick={onLogout} title="Uitloggen" />
          </div>
        </div>
      </header>
      <div className="border-b border-line bg-panel">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-end gap-2 px-4 py-3">{actions}</div>
      </div>
      <main className="mx-auto max-w-7xl px-4 py-5">{children}</main>
    </div>
  );
}

function Dashboard({api, user, onLogout, openBatch}) {
  const fileRef = useRef(null);
  const [batches, setBatches] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const list = await api.batches();
    const withLabels = await Promise.all(list.map(async (batch) => {
      try {
        return {...batch, ...(await api.batch(batch.id))};
      } catch {
        return batch;
      }
    }));
    setBatches(withLabels.sort((a, b) => String(b.id).localeCompare(String(a.id))));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    const timer = window.setInterval(() => load().catch(() => {}), 3000);
    return () => window.clearInterval(timer);
  }, []);

  async function upload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const naam = file.name.replace(/\.[^.]+$/, "");
      const created = await api.uploadBatch(file, naam, new Date().getFullYear());
      await load();
      openBatch(created.batch_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  async function run(batchId) {
    setBusy(true);
    try {
      await api.runBatch(batchId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function cancel(batchId) {
    setBusy(true);
    try {
      await api.cancelBatch(batchId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title="Dashboard"
      actions={
        <>
          <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={upload} />
          <IconButton icon={RefreshCw} onClick={() => load().catch((err) => setError(err.message))}>Verversen</IconButton>
          <IconButton icon={FileUp} variant="primary" onClick={() => fileRef.current?.click()} disabled={busy}>CSV uploaden</IconButton>
        </>
      }
    >
      {error ? <Alert message={error} /> : null}
      <div className="overflow-hidden rounded-lg border border-line bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-panel text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Batch</th>
              <th className="px-4 py-3">Voortgang</th>
              <th className="px-4 py-3">Labels</th>
              <th className="px-4 py-3">Status</th>
              <th className="w-32 px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {batches.map((batch) => (
              <tr key={batch.id} className="border-t border-line hover:bg-panel">
                <td className="px-4 py-3">
                  <button className="focus-ring rounded text-left font-semibold text-etil" onClick={() => openBatch(batch.id)}>
                    {batch.naam || batch.id}
                  </button>
                  <div className="text-xs text-slate-500">{batch.jaar}</div>
                </td>
                <td className="px-4 py-3">
                  <Progress value={batch.verwerkt || 0} total={batch.totaal || 0} />
                </td>
                <td className="px-4 py-3">
                  <LabelCounts labels={batch.labels} />
                </td>
                <td className="px-4 py-3"><StatusPill status={batch.status} /></td>
                <td className="px-4 py-3 text-right">
                  {batch.status === "running"
                    ? <IconButton icon={Square} variant="quiet" onClick={() => cancel(batch.id)} disabled={busy}>Annuleren</IconButton>
                    : <IconButton icon={Play} onClick={() => run(batch.id)} disabled={busy}>Run</IconButton>
                  }
                </td>
              </tr>
            ))}
            {!batches.length ? (
              <tr>
                <td className="px-4 py-8 text-center text-slate-500" colSpan="5">Geen batches</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}

function BatchView({api, user, onLogout, batchId, openDashboard, openCompany}) {
  const [batch, setBatch] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [label, setLabel] = useState("");
  const [strategie, setStrategie] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const [batchData, companyData] = await Promise.all([api.batch(batchId), api.companies(batchId, label)]);
    setBatch(batchData);
    setCompanies(companyData);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    const timer = window.setInterval(() => load().catch(() => {}), 3000);
    return () => window.clearInterval(timer);
  }, [batchId, label]);

  const filtered = useMemo(() => companies.filter((company) => {
    const matchesStrategie = !strategie || company.strategie === strategie;
    const text = `${company.naam || ""} ${company.gemeente || ""}`.toLowerCase();
    return matchesStrategie && text.includes(search.toLowerCase());
  }), [companies, strategie, search]);

  async function approveAll() {
    try {
      await api.approveAllGreen(batchId);
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function runBatch() {
    setBusy(true);
    setError("");
    try {
      await api.runBatch(batchId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function cancelBatch() {
    setBusy(true);
    setError("");
    try {
      await api.cancelBatch(batchId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const isRunning = batch?.status === "running";

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title={batch?.naam || "Batch"}
      actions={
        <>
          <IconButton icon={ListChecks} onClick={openDashboard}>Dashboard</IconButton>
          {isRunning
            ? <IconButton icon={Square} variant="quiet" onClick={cancelBatch} disabled={busy}>Annuleren</IconButton>
            : <IconButton icon={Play} variant="primary" onClick={runBatch} disabled={busy}>Run</IconButton>
          }
          <IconButton icon={Check} onClick={approveAll} disabled={isRunning}>Groen goedkeuren</IconButton>
          <IconButton icon={FileDown} onClick={() => api.download(`/batches/${batchId}/export.csv`, "export.csv")}>Export</IconButton>
          <IconButton icon={Download} onClick={() => api.download(`/batches/${batchId}/bellijst.csv`, "bellijst.csv")}>Bellijst</IconButton>
        </>
      }
    >
      {error ? <Alert message={error} /> : null}
      <div className="mb-4 grid gap-3 md:grid-cols-[1fr_180px_220px]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-3 text-slate-400" size={17} />
          <input className="focus-ring h-11 w-full rounded-md border border-line bg-white pl-9 pr-3" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Zoeken" />
        </div>
        <select className="focus-ring h-11 rounded-md border border-line bg-white px-3" value={label} onChange={(event) => setLabel(event.target.value)}>
          <option value="">Alle labels</option>
          <option value="hoog">Groen</option>
          <option value="middel">Geel</option>
          <option value="laag">Rood</option>
        </select>
        <select className="focus-ring h-11 rounded-md border border-line bg-white px-3" value={strategie} onChange={(event) => setStrategie(event.target.value)}>
          <option value="">Alle strategieen</option>
          {Object.entries(STRATEGIE_LABELS).map(([value, text]) => <option key={value} value={value}>{text}</option>)}
        </select>
      </div>
      {batch ? (
        <div className="mb-4 grid gap-3 md:grid-cols-3">
          <Metric title="Voortgang" value={`${batch.verwerkt || 0}/${batch.totaal || 0}`} />
          <Metric title="Status" value={<StatusPill status={batch.status} />} />
          <Metric title="Labels" value={<LabelCounts labels={batch.labels} />} />
        </div>
      ) : null}
      <div className="overflow-hidden rounded-lg border border-line bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-panel text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Vestiging</th>
              <th className="px-4 py-3">WP</th>
              <th className="px-4 py-3">Confidence</th>
              <th className="px-4 py-3">Strategie</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((company) => (
              <tr key={company.company_id} className="cursor-pointer border-t border-line hover:bg-panel" onClick={() => openCompany(batchId, company.company_id)}>
                <td className="px-4 py-3">
                  <div className="font-semibold">{company.naam}</div>
                  <div className="text-xs text-slate-500">{company.gemeente}</div>
                </td>
                <td className="px-4 py-3 font-medium">{company.wp_kandidaat ?? "-"}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3">
                    <LabelBadge label={company.confidence_label} />
                    <span className="text-xs text-slate-500">{pct(company.confidence_score)}%</span>
                  </div>
                </td>
                <td className="px-4 py-3">{STRATEGIE_LABELS[company.strategie] || company.strategie || "-"}</td>
                <td className="px-4 py-3"><StatusPill status={company.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}

function DetailView({api, user, onLogout, batchId, companyId, openBatch}) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const [correctWp, setCorrectWp] = useState("");
  const [reason, setReason] = useState("");

  async function load() {
    setDetail(await api.company(batchId, companyId));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, [batchId, companyId]);

  const candidate = detail?.candidate;

  async function action(fn) {
    setError("");
    try {
      await fn();
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title={detail?.company?.naam || "Vestiging"}
      actions={<IconButton icon={ListChecks} onClick={() => openBatch(batchId)}>Batchoverzicht</IconButton>}
    >
      {error ? <Alert message={error} /> : null}
      {detail ? (
        <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
          <section className="space-y-5">
            <Panel title="Vestigingsgegevens">
              <dl className="grid gap-3 text-sm sm:grid-cols-2">
                <Info label="Naam" value={detail.company.naam} />
                <Info label="Gemeente" value={detail.company.gemeente} />
                <Info label="Adres" value={detail.company.adres} />
                <Info label="SBI" value={detail.company.sbi_code} />
                <Info label="CB-er" value={detail.company.cb_er || "-"} />
                <Info label="KvK" value={detail.company.kvk_nummer || "-"} />
              </dl>
            </Panel>
            <Panel title="Gevonden bronnen">
              <div className="space-y-3">
                {detail.agent_results.map((result, index) => (
                  <div key={`${result.agent_type}-${index}`} className="rounded-md border border-line bg-panel p-3">
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                      <div className="font-semibold">{result.agent_type} - WP {result.wp_gevonden ?? "-"}</div>
                      <div className="text-xs text-slate-500">{result.bron_type} - {result.peilmoment || "geen peilmoment"}</div>
                    </div>
                    <blockquote className="border-l-4 border-etil pl-3 text-sm text-slate-700">{result.context || "Geen citaat"}</blockquote>
                    {result.bron_url ? (
                      <a className="mt-2 inline-block text-sm font-medium text-etil underline" href={result.bron_url} target="_blank" rel="noreferrer">Bron openen</a>
                    ) : null}
                  </div>
                ))}
                {!detail.agent_results.length ? <div className="text-sm text-slate-500">Geen bronresultaten</div> : null}
              </div>
            </Panel>
            <Panel title="Score-uitleg">
              <ScoreBreakdown breakdown={candidate?.score_breakdown} />
            </Panel>
          </section>
          <aside className="space-y-5">
            <Panel title="Kandidaat">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <div className="text-3xl font-semibold">{candidate?.wp_kandidaat ?? "-"}</div>
                  <div className="text-sm text-slate-500">Werkzame personen</div>
                </div>
                <LabelBadge label={candidate?.confidence_label} />
              </div>
              <Progress value={pct(candidate?.confidence_score)} total={100} />
              {candidate?.is_schatting ? (
                <div className="mt-3 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                  <AlertTriangle size={17} /> Schatting: niet geschikt voor groen.
                </div>
              ) : null}
              <div className="mt-4 border-t border-line pt-4 text-sm">
                <div className="mb-1 font-semibold">Reconciliatie</div>
                <p className="text-slate-700">{candidate?.reconciliatie_reden || "-"}</p>
              </div>
            </Panel>
            <Panel title="Review">
              <div className="space-y-3">
                <IconButton icon={Check} variant="primary" className="w-full justify-center" disabled={!candidate?.wp_kandidaat} onClick={() => action(() => api.approve(candidate.id))}>
                  Goedkeuren
                </IconButton>
                <input className="focus-ring h-10 w-full rounded-md border border-line px-3" value={correctWp} onChange={(event) => setCorrectWp(event.target.value)} placeholder="Gecorrigeerde WP" inputMode="numeric" />
                <textarea className="focus-ring min-h-24 w-full rounded-md border border-line px-3 py-2" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Reden" />
                <div className="grid grid-cols-2 gap-2">
                  <IconButton icon={Check} disabled={!correctWp || !candidate} onClick={() => action(() => api.correct(candidate.id, correctWp, reason))}>
                    Corrigeren
                  </IconButton>
                  <IconButton icon={Phone} disabled={!candidate} onClick={() => action(() => api.bellijst(candidate.id, reason))}>
                    Bellijst
                  </IconButton>
                </div>
              </div>
            </Panel>
          </aside>
        </div>
      ) : null}
    </Shell>
  );
}

function Panel({title, children}) {
  return (
    <section className="rounded-lg border border-line bg-white p-4 shadow-sm">
      <h2 className="mb-4 text-base font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Info({label, value}) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase text-slate-500">{label}</dt>
      <dd className="mt-1 break-words font-medium">{value || "-"}</dd>
    </div>
  );
}

function Metric({title, value}) {
  return (
    <div className="rounded-lg border border-line bg-white p-4">
      <div className="mb-2 text-xs font-medium uppercase text-slate-500">{title}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}

function Progress({value, total}) {
  const width = total ? Math.round((value / total) * 100) : 0;
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-500">
        <span>{value}</span>
        <span>{total}</span>
      </div>
      <div className="h-2 rounded-full bg-slate-200">
        <div className="h-2 rounded-full bg-etil" style={{width: `${Math.max(0, Math.min(100, width))}%`}} />
      </div>
    </div>
  );
}

function LabelCounts({labels = {}}) {
  return (
    <div className="flex flex-wrap gap-2">
      {["hoog", "middel", "laag"].map((label) => (
        <span key={label} className="inline-flex items-center gap-1 rounded-md border border-line bg-white px-2 py-1 text-xs">
          <span className={classNames("h-2 w-2 rounded-full", LABELS[label].dot)} />
          {labels?.[label] || 0}
        </span>
      ))}
    </div>
  );
}

function ScoreBreakdown({breakdown}) {
  if (!breakdown) return <div className="text-sm text-slate-500">Geen score beschikbaar</div>;
  const rows = Object.entries(breakdown).filter(([key, value]) => key !== "penalties" && typeof value === "object");
  const penalties = breakdown.penalties || {};
  return (
    <div className="space-y-3">
      {rows.map(([key, value]) => (
        <div key={key}>
          <div className="mb-1 flex items-center justify-between text-sm">
            <span className="capitalize">{key}</span>
            <span className="font-medium">{pct(value.factor)}% x {pct(value.gewicht)}%</span>
          </div>
          <div className="h-2 rounded-full bg-slate-200">
            <div className="h-2 rounded-full bg-etil" style={{width: `${pct(value.factor)}%`}} />
          </div>
        </div>
      ))}
      {Object.keys(penalties).length ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {Object.entries(penalties).map(([key, value]) => (
            <div key={key} className="flex justify-between gap-3">
              <span>{key.replaceAll("_", " ")}</span>
              <span>-{pct(value)}%</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Alert({message}) {
  return (
    <div className="mb-4 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      <X size={17} />
      <span>{message}</span>
    </div>
  );
}

export default function App() {
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
    />
  );
}
