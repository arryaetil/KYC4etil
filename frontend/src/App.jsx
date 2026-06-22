import {useEffect, useMemo, useRef, useState} from "react";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronUp,
  Download,
  FileDown,
  FileUp,
  GripVertical,
  ListChecks,
  LogOut,
  Mail,
  MessageSquare,
  Phone,
  Play,
  Plus,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Square,
  Trash2,
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

function Dashboard({api, user, onLogout, openBatch, openChatTemplates}) {
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
    setBatches(withLabels.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")));
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

  async function deleteBatch(batchId, naam) {
    if (!window.confirm(`Batch "${naam}" definitief verwijderen?`)) return;
    setBusy(true);
    try {
      await api.deleteBatch(batchId);
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
          <IconButton icon={Settings} variant="quiet" onClick={openChatTemplates}>Chat-templates</IconButton>
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
              <th className="px-4 py-3">Aangemaakt</th>
              <th className="px-4 py-3">Voortgang</th>
              <th className="px-4 py-3">Labels</th>
              <th className="px-4 py-3">Status</th>
              <th className="w-40 px-4 py-3"></th>
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
                <td className="px-4 py-3 text-sm text-slate-600">
                  <BatchTimestamp created_at={batch.created_at} completed_at={batch.completed_at} />
                </td>
                <td className="px-4 py-3">
                  <Progress value={batch.verwerkt || 0} total={batch.totaal || 0} />
                </td>
                <td className="px-4 py-3">
                  <LabelCounts labels={batch.labels} />
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusPill status={batch.status} />
                    {batch.fouten > 0 && (
                      <span className="inline-flex items-center gap-1 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs font-semibold text-red-700">
                        <AlertTriangle size={11} />{batch.fouten}
                      </span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="inline-flex items-center gap-2">
                    {batch.status === "running"
                      ? <IconButton icon={Square} variant="quiet" onClick={() => cancel(batch.id)} disabled={busy}>Annuleren</IconButton>
                      : <IconButton icon={Play} onClick={() => run(batch.id)} disabled={busy}>Run</IconButton>
                    }
                    <IconButton icon={Trash2} variant="quiet" onClick={() => deleteBatch(batch.id, batch.naam)} disabled={busy || batch.status === "running"} title="Batch verwijderen" />
                  </div>
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

function BatchView({api, user, onLogout, batchId, openDashboard, openCompany, openBellijst, openChatSessies}) {
  const [batch, setBatch] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [label, setLabel] = useState("");
  const [strategie, setStrategie] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const labelParam = label === "fouten" ? "" : label;
    const [batchData, companyData] = await Promise.all([
      api.batch(batchId),
      api.companies(batchId, labelParam),
    ]);
    setBatch(batchData);
    setCompanies(companyData);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    const timer = window.setInterval(() => load().catch(() => {}), 3000);
    return () => window.clearInterval(timer);
  }, [batchId, label]);

  const filtered = useMemo(() => companies.filter((company) => {
    if (label === "fouten") return !!company.pipeline_error;
    const matchesStrategie = !strategie || company.strategie === strategie;
    const text = `${company.naam || ""} ${company.gemeente || ""}`.toLowerCase();
    return matchesStrategie && text.includes(search.toLowerCase());
  }), [companies, label, strategie, search]);

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

  async function resetVastgelopen() {
    if (!window.confirm("Batch terugzetten naar 'pending'?\n\nAlleen doen als de server herstart is en de taak echt niet meer draait.")) return;
    setBusy(true);
    setError("");
    try {
      await api.resetVastgelopen(batchId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function deleteBatch() {
    if (!window.confirm(`Batch "${batch?.naam}" definitief verwijderen?`)) return;
    setBusy(true);
    try {
      await api.deleteBatch(batchId);
      openDashboard();
    } catch (err) {
      setError(err.message);
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
          {isRunning ? (
            <>
              <IconButton icon={Square} variant="quiet" onClick={cancelBatch} disabled={busy}>Annuleren</IconButton>
              <IconButton icon={RefreshCw} variant="quiet" onClick={resetVastgelopen} disabled={busy} title="Gebruik alleen na server-herstart als de taak niet meer draait">Vastgelopen?</IconButton>
            </>
          ) : (
            <IconButton icon={Play} variant="primary" onClick={runBatch} disabled={busy}>Run</IconButton>
          )}
          <IconButton icon={Check} onClick={approveAll} disabled={isRunning}>Groen goedkeuren</IconButton>
          <IconButton icon={FileDown} onClick={() => api.download(`/batches/${batchId}/export.csv`, "export.csv")}>Export</IconButton>
          <IconButton icon={Phone} onClick={() => openBellijst(batchId)}>Bellijst</IconButton>
          <IconButton icon={MessageSquare} onClick={() => openChatSessies(batchId)}>Chat-sessies</IconButton>
          <IconButton icon={Trash2} variant="quiet" onClick={deleteBatch} disabled={busy || isRunning} title="Batch verwijderen" />
        </>
      }
    >
      {error ? <Alert message={error} /> : null}
      <div className="mb-4 grid gap-3 md:grid-cols-[1fr_180px_220px]">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-3 text-slate-400" size={17} />
          <input className="focus-ring h-11 w-full rounded-md border border-line bg-white pl-9 pr-3" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Zoeken" />
        </div>
        <select className={classNames(
          "focus-ring h-11 rounded-md border bg-white px-3",
          label === "fouten" ? "border-red-400 text-red-700 font-medium" : "border-line",
        )} value={label} onChange={(event) => setLabel(event.target.value)}>
          <option value="">Alle labels</option>
          <option value="hoog">Groen</option>
          <option value="middel">Geel</option>
          <option value="laag">Rood</option>
          <option value="fouten">{batch?.fouten > 0 ? `Fouten (${batch.fouten})` : "Fouten"}</option>
        </select>
        <select className="focus-ring h-11 rounded-md border border-line bg-white px-3" value={strategie} onChange={(event) => setStrategie(event.target.value)}>
          <option value="">Alle strategieen</option>
          {Object.entries(STRATEGIE_LABELS).map(([value, text]) => <option key={value} value={value}>{text}</option>)}
        </select>
      </div>
      {batch ? (
        <div className="mb-4 grid gap-3 md:grid-cols-3">
          <Metric title="Voortgang" value={`${batch.verwerkt || 0}/${batch.totaal || 0}`} />
          <Metric title="Status" value={
            <div className="flex items-center gap-2">
              <StatusPill status={batch.status} />
              {batch.fouten > 0 && (
                <span className="inline-flex items-center gap-1 rounded-md border border-red-200 bg-red-50 px-2 py-1 text-xs font-semibold text-red-700">
                  <AlertTriangle size={12} />{batch.fouten} {batch.fouten === 1 ? "fout" : "fouten"}
                </span>
              )}
            </div>
          } />
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
                  <div className="flex items-center gap-2">
                    <div className="font-semibold">{company.naam}</div>
                    {company.pipeline_error && <AlertTriangle size={14} className="shrink-0 text-red-500" />}
                  </div>
                  <div className="text-xs text-slate-500">{company.gemeente}</div>
                  {company.pipeline_error && (
                    <div className="mt-1 max-w-xs truncate text-xs font-medium text-red-600" title={company.pipeline_error}>
                      {company.pipeline_error}
                    </div>
                  )}
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

const BELLIJST_STATUS = {
  open: {label: "Open", cls: "bg-slate-100 text-slate-700"},
  gebeld: {label: "Gebeld", cls: "bg-blue-100 text-blue-800"},
  niet_bereikt: {label: "Niet bereikt", cls: "bg-amber-100 text-amber-800"},
  afgerond: {label: "Afgerond", cls: "bg-emerald-100 text-emerald-800"},
};

function BellijstView({api, user, onLogout, batchId, openBatch}) {
  const [items, setItems] = useState([]);
  const [edits, setEdits] = useState({});
  const [saving, setSaving] = useState({});
  const [doorgevoerd, setDoorgevoerd] = useState({});
  const [filterStatus, setFilterStatus] = useState("");
  const [sortField, setSortField] = useState("naam");
  const [error, setError] = useState("");

  async function load() {
    const data = await api.bellijstItems(batchId);
    setItems(data);
    const init = {};
    data.forEach((item) => {
      init[item.id] = {status: item.status, notities: item.notities || "", resultaat_wp: item.resultaat_wp ?? ""};
    });
    setEdits(init);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, [batchId]);

  function patch(id, field, value) {
    setEdits((prev) => ({...prev, [id]: {...prev[id], [field]: value}}));
  }

  async function save(id) {
    setSaving((prev) => ({...prev, [id]: true}));
    try {
      const e = edits[id];
      await api.updateBellijstItem(id, {
        status: e.status,
        notities: e.notities || null,
        resultaat_wp: e.resultaat_wp !== "" ? Number(e.resultaat_wp) : null,
      });
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving((prev) => ({...prev, [id]: false}));
    }
  }

  async function doorvoeren(id) {
    setSaving((prev) => ({...prev, [`dv_${id}`]: true}));
    try {
      await api.doorvoerenBellijst(id);
      setDoorgevoerd((prev) => ({...prev, [id]: true}));
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving((prev) => ({...prev, [`dv_${id}`]: false}));
    }
  }

  const visibleItems = useMemo(() => {
    let list = filterStatus ? items.filter((i) => i.status === filterStatus) : items;
    return [...list].sort((a, b) => {
      if (sortField === "naam") return (a.naam || "").localeCompare(b.naam || "");
      if (sortField === "status") return (a.status || "").localeCompare(b.status || "");
      return 0;
    });
  }, [items, filterStatus, sortField]);

  const open = items.filter((i) => i.status === "open").length;
  const afgerond = items.filter((i) => i.status === "afgerond").length;

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title="Bellijst werkscherm"
      actions={
        <>
          <IconButton icon={ListChecks} onClick={() => openBatch(batchId)}>Batchoverzicht</IconButton>
          <IconButton icon={Download} onClick={() => api.download(`/batches/${batchId}/bellijst.csv`, "bellijst.csv")}>Exporteren</IconButton>
        </>
      }
    >
      {error ? <Alert message={error} /> : null}
      <div className="mb-4 grid gap-3 md:grid-cols-3">
        <Metric title="Totaal" value={items.length} />
        <Metric title="Open" value={open} />
        <Metric title="Afgerond" value={afgerond} />
      </div>
      {items.length > 0 && (
        <div className="mb-4 flex flex-wrap gap-3">
          <select className="focus-ring h-10 rounded-md border border-line bg-white px-3 text-sm" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)}>
            <option value="">Alle statussen</option>
            {Object.entries(BELLIJST_STATUS).map(([v, {label}]) => <option key={v} value={v}>{label}</option>)}
          </select>
          <select className="focus-ring h-10 rounded-md border border-line bg-white px-3 text-sm" value={sortField} onChange={(e) => setSortField(e.target.value)}>
            <option value="naam">Sorteren: naam</option>
            <option value="status">Sorteren: status</option>
          </select>
          <span className="ml-auto self-center text-sm text-slate-500">{visibleItems.length} van {items.length}</span>
        </div>
      )}
      {!items.length ? (
        <div className="rounded-lg border border-line bg-white p-8 text-center text-slate-500">Geen items op de bellijst</div>
      ) : (
        <div className="space-y-3">
          {visibleItems.map((item) => {
            const e = edits[item.id] || {};
            const cfg = BELLIJST_STATUS[e.status] || BELLIJST_STATUS.open;
            return (
              <div key={item.id} className="rounded-lg border border-line bg-white p-4">
                <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="font-semibold">{item.naam}</div>
                    <div className="text-sm text-slate-500">{item.gemeente}</div>
                    {item.telefoonnummer ? (
                      <a className="mt-1 inline-flex items-center gap-1 text-sm font-medium text-etil" href={`tel:${item.telefoonnummer}`}>
                        <Phone size={14} />{item.telefoonnummer}
                      </a>
                    ) : <div className="mt-1 text-sm text-slate-400">Geen telefoonnummer</div>}
                    {item.email ? (
                      <a className="mt-1 inline-flex items-center gap-1 text-sm font-medium text-etil" href={`mailto:${item.email}`}>
                        <Mail size={14} />{item.email}
                      </a>
                    ) : null}
                  </div>
                  <span className={classNames("rounded-md px-2 py-1 text-xs font-semibold", cfg.cls)}>{cfg.label}</span>
                </div>
                {item.reden ? (
                  <div className="mb-3 rounded-md border-l-4 border-etil bg-panel pl-3 py-2 text-sm text-slate-700">{item.reden}</div>
                ) : null}
                <div className="grid gap-3 md:grid-cols-[160px_1fr_140px_100px]">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-500">Status</label>
                    <select
                      className="focus-ring h-10 w-full rounded-md border border-line bg-white px-2 text-sm"
                      value={e.status || "open"}
                      onChange={(ev) => patch(item.id, "status", ev.target.value)}
                    >
                      {Object.entries(BELLIJST_STATUS).map(([value, {label}]) => (
                        <option key={value} value={value}>{label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-500">Notities</label>
                    <input
                      className="focus-ring h-10 w-full rounded-md border border-line px-3 text-sm"
                      value={e.notities || ""}
                      onChange={(ev) => patch(item.id, "notities", ev.target.value)}
                      placeholder="Notitie toevoegen…"
                    />
                  </div>
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-500">Resultaat WP</label>
                    <input
                      className="focus-ring h-10 w-full rounded-md border border-line px-3 text-sm"
                      value={e.resultaat_wp ?? ""}
                      onChange={(ev) => patch(item.id, "resultaat_wp", ev.target.value)}
                      placeholder="WP"
                      inputMode="numeric"
                    />
                  </div>
                  <div className="flex items-end">
                    <IconButton
                      icon={Check}
                      variant="primary"
                      className="w-full justify-center"
                      onClick={() => save(item.id)}
                      disabled={saving[item.id]}
                    >
                      {saving[item.id] ? "…" : "Opslaan"}
                    </IconButton>
                  </div>
                </div>
                {item.status === "afgerond" && item.resultaat_wp != null ? (
                  <div className="mt-3 flex items-center justify-between border-t border-line pt-3">
                    <span className="text-sm text-slate-500">
                      Resultaat <strong>{item.resultaat_wp} WP</strong> — doorvoeren naar register?
                    </span>
                    {doorgevoerd[item.id] ? (
                      <span className="inline-flex items-center gap-1 text-sm font-medium text-emerald-700"><Check size={15} /> Doorgevoerd</span>
                    ) : (
                      <IconButton icon={Check} variant="primary" onClick={() => doorvoeren(item.id)} disabled={saving[`dv_${item.id}`]}>
                        {saving[`dv_${item.id}`] ? "…" : "Doorvoeren"}
                      </IconButton>
                    )}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </Shell>
  );
}

function DetailView({api, user, onLogout, batchId, companyId, openBatch}) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");
  const [correctWp, setCorrectWp] = useState("");
  const [reason, setReason] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatResult, setChatResult] = useState(null);

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
              {detail.enrichment ? <EnrichmentStrip enrichment={detail.enrichment} /> : null}
            </Panel>
            <WpUitsplitsing wp_historie={detail?.wp_historie} />
            <VastgoedKaart api={api} batchId={batchId} companyId={companyId} vastgoed={detail?.vastgoed} />
            <WpHistorie wp_historie={detail?.wp_historie} />
            <Panel title="Gevonden bronnen">
              <div className="space-y-3">
                {detail.agent_results.map((result, index) => (
                  <div key={`${result.agent_type}-${index}`} className="rounded-md border border-line bg-panel p-3">
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                      <div className="font-semibold">{result.agent_type} — WP {result.wp_gevonden ?? "-"}</div>
                      <div className="flex flex-wrap items-center gap-2">
                        {result.llm_zekerheid ? (
                          <span className={classNames("rounded px-1.5 py-0.5 text-xs font-semibold capitalize", ZEKERHEID_STYLE[result.llm_zekerheid] || ZEKERHEID_STYLE.laag)}>
                            {result.llm_zekerheid}
                          </span>
                        ) : null}
                        {result.is_limburg_specifiek === true && (
                          <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-xs font-semibold text-emerald-800">LB-specifiek</span>
                        )}
                        {result.is_limburg_specifiek === false && (
                          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-semibold text-amber-800">Nationaal</span>
                        )}
                        {result.is_fte && (
                          <span className="rounded bg-red-100 px-1.5 py-0.5 text-xs font-semibold text-red-800">FTE</span>
                        )}
                        <span className="text-xs text-slate-500">{result.bron_type} · {result.peilmoment || "geen peilmoment"}</span>
                      </div>
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
              <ScoreBreakdown breakdown={candidate?.score_breakdown} label={candidate?.confidence_label} />
            </Panel>
            <VorigJaarVergelijking vorig_jaar={detail?.vorig_jaar} huidig_wp={candidate?.wp_kandidaat} />
            {detail.pipeline_fouten?.length > 0 && (
              <Panel title="Pipeline-fouten">
                <div className="space-y-2">
                  {detail.pipeline_fouten.map((f, i) => (
                    <div key={i} className="rounded-md border border-red-200 bg-red-50 p-3 text-sm">
                      <div className="mb-1 flex items-center gap-2 font-semibold text-red-800">
                        <AlertTriangle size={14} />{f.stap}
                      </div>
                      <pre className="overflow-x-auto whitespace-pre-wrap break-all font-mono text-xs text-red-700">{f.error}</pre>
                    </div>
                  ))}
                </div>
              </Panel>
            )}
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
                {chatResult ? (
                  <div className="space-y-2">
                    {chatResult.ok ? (
                      <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                        <strong>Email verstuurd</strong> naar {chatResult.recipient}
                      </div>
                    ) : null}
                    <div className="rounded-md border border-line bg-panel p-3">
                      <div className="mb-1 text-xs font-medium text-slate-500">Chat-link</div>
                      <a
                        className="block break-all text-sm font-medium text-etil underline"
                        href={chatResult.chatUrl}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {chatResult.chatUrl}
                      </a>
                      <button
                        className="mt-2 text-xs text-slate-500 underline"
                        onClick={() => navigator.clipboard.writeText(chatResult.chatUrl)}
                      >
                        Kopieer link
                      </button>
                    </div>
                  </div>
                ) : (
                  <IconButton
                    icon={Mail}
                    className="w-full justify-center"
                    disabled={!candidate || chatBusy}
                    onClick={async () => {
                      setChatBusy(true);
                      try {
                        const res = await api.createChatSession(candidate.id);
                        setChatResult({ok: res.email_sent, recipient: res.email_recipient, chatUrl: res.chat_url});
                        await load();
                      } catch (err) {
                        setError(err.message);
                      } finally {
                        setChatBusy(false);
                      }
                    }}
                  >
                    {chatBusy ? "Bezig…" : "Verstuur chat-uitnodiging"}
                  </IconButton>
                )}
                <div className="border-t border-line pt-3">
                  <IconButton icon={RefreshCw} className="w-full justify-center" onClick={() => action(() => api.herverwerk(batchId, companyId))}>
                    Herverwerk
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

function EnrichmentStrip({enrichment}) {
  const website = enrichment.website_url;
  const tel = enrichment.telefoonnummer;
  const email = enrichment.email;
  const nlCount = enrichment.locatie_count_nl;
  const lbCount = enrichment.locatie_count_lb;
  const bron = enrichment.locatie_bron;
  const bronLabel = {places: "Places", kvk: "KvK", web_search: "web search"}[bron] || bron;

  const hasAny = website || tel || email || nlCount;
  if (!hasAny) return null;

  return (
    <div className="mt-4 border-t border-line pt-4">
      <div className="mb-2 text-xs font-medium uppercase text-slate-500">Gevonden door agent</div>
      <div className="flex flex-wrap gap-4 text-sm">
        {website ? (
          <div>
            <span className="text-slate-500">Website </span>
            <a className="font-medium text-etil underline" href={website} target="_blank" rel="noreferrer">{website.replace(/^https?:\/\//, "")}</a>
          </div>
        ) : null}
        {tel ? (
          <div>
            <span className="text-slate-500">Tel </span>
            <span className="font-medium">{tel}</span>
          </div>
        ) : null}
        {email ? (
          <div>
            <span className="text-slate-500">E-mail </span>
            <a className="font-medium text-etil underline" href={`mailto:${email}`}>{email}</a>
          </div>
        ) : null}
        {nlCount != null ? (
          <div>
            <span className="text-slate-500">Locaties </span>
            <span className="font-medium">{lbCount ?? "?"} in LB / {nlCount} NL</span>
            {bronLabel ? <span className="ml-1 text-xs text-slate-400">({bronLabel})</span> : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}

const ZEKERHEID_STYLE = {
  hoog: "bg-emerald-100 text-emerald-800",
  middel: "bg-amber-100 text-amber-800",
  laag: "bg-red-100 text-red-800",
};

const BREAKDOWN_NL = {
  fte_only: "FTE opgegeven, geen WP — niet 1:1 vergelijkbaar",
  proportionele_schatting: "Proportionele schatting — inherent onzeker",
  places_fuzzy: "Locatiecount via Google Places, niet KvK-exact",
  consensus: "Bevestigd door meerdere onafhankelijke bronnen",
};

function ScoreBreakdown({breakdown, label}) {
  if (!breakdown) return <div className="text-sm text-slate-500">Geen score beschikbaar</div>;

  if (!breakdown.zekerheid_llm) {
    return (
      <div className="rounded-md border border-slate-200 bg-panel p-3 text-sm text-slate-700">
        <div className="mb-1 text-xs font-medium uppercase text-slate-500">Geen agent-data gevonden</div>
        {breakdown.reden || "Geen reden opgegeven"}
      </div>
    );
  }

  const zekerheid = breakdown.zekerheid_llm;
  const base = breakdown.base_score;
  const bonuses = breakdown.bonuses || {};
  const penalties = breakdown.penalties || {};
  const hasBonuses = Object.keys(bonuses).length > 0;
  const hasPenalties = Object.keys(penalties).length > 0;
  const isNietGroen = label === "middel" || label === "laag";

  return (
    <div className="space-y-3 text-sm">
      {isNietGroen && (hasPenalties || zekerheid !== "hoog") ? (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-amber-900">
          <div className="mb-1.5 font-semibold text-xs uppercase">Waarom niet groen?</div>
          <ul className="space-y-1">
            {zekerheid !== "hoog" ? (
              <li className="flex items-start gap-1.5">
                <span className="mt-0.5 shrink-0 text-amber-500">▸</span>
                LLM-zekerheid is <strong>{zekerheid}</strong> — basesscore {pct(base)}%
              </li>
            ) : null}
            {Object.keys(penalties).map((key) => (
              <li key={key} className="flex items-start gap-1.5">
                <span className="mt-0.5 shrink-0 text-amber-500">▸</span>
                {BREAKDOWN_NL[key] || key.replaceAll("_", " ")}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="flex items-center justify-between">
        <span className="text-slate-500">LLM-zekerheid</span>
        <span className={classNames("rounded-md px-2 py-0.5 font-semibold capitalize", ZEKERHEID_STYLE[zekerheid] || ZEKERHEID_STYLE.laag)}>
          {zekerheid || "onbekend"}
        </span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-slate-500">Basisscore</span>
        <span className="font-medium">{pct(base)}%</span>
      </div>
      <div className="flex items-center justify-between">
        <span className="text-slate-500">Bron</span>
        <span>{breakdown.bron_type || "-"}{breakdown.n_bronnen > 1 ? ` · ${breakdown.n_bronnen} bronnen` : ""}</span>
      </div>
      {hasBonuses ? (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3">
          {Object.entries(bonuses).map(([key, value]) => (
            <div key={key} className="flex justify-between gap-3 text-emerald-800 text-xs">
              <span>{BREAKDOWN_NL[key] || key.replaceAll("_", " ")}</span>
              <span className="shrink-0 font-semibold">+{pct(value)}%</span>
            </div>
          ))}
        </div>
      ) : null}
      {hasPenalties ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-red-900">
          {Object.entries(penalties).map(([key, value]) => (
            <div key={key} className="flex justify-between gap-3 text-xs">
              <span>{BREAKDOWN_NL[key] || key.replaceAll("_", " ")}</span>
              <span className="shrink-0 font-semibold">-{pct(value)}%</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

const BRON_TAG = {
  chat:      {label: "Via chat",      cls: "bg-blue-50 text-blue-600 border-blue-200"},
  belactie:  {label: "Via belactie",  cls: "bg-amber-50 text-amber-600 border-amber-200"},
  handmatig: {label: "Handmatig",     cls: "bg-slate-50 text-slate-500 border-slate-200"},
  pipeline:  {label: "Via pipeline",  cls: "bg-violet-50 text-violet-600 border-violet-200"},
};

function BronTag({bron}) {
  const cfg = BRON_TAG[bron] || BRON_TAG.handmatig;
  return (
    <span className={classNames("rounded border px-1.5 py-0.5 text-xs font-medium", cfg.cls)}>
      {cfg.label}
    </span>
  );
}

function KennisVeld({label, value, unit, bron}) {
  const isEmpty = value === null || value === undefined || value === "";
  return (
    <div>
      <dt className="mb-0.5 text-xs font-medium uppercase text-slate-400">{label}</dt>
      {isEmpty ? (
        <dd className="flex items-center gap-1.5">
          <span className="text-slate-300">—</span>
          {bron && <BronTag bron={bron} />}
        </dd>
      ) : (
        <dd className="font-semibold text-slate-800">
          {unit ? `${value} ${unit}` : String(value === true ? "Ja" : value === false ? "Nee" : value)}
        </dd>
      )}
    </div>
  );
}

function Volledigheid({gevuld, totaal}) {
  const pctVal = totaal ? Math.round((gevuld / totaal) * 100) : 0;
  const kleur = pctVal === 100 ? "bg-emerald-500" : pctVal >= 50 ? "bg-amber-400" : "bg-red-400";
  return (
    <div className="mb-4 flex items-center gap-3 rounded-md border border-line bg-panel px-3 py-2">
      <div className="flex-1">
        <div className="mb-1 flex justify-between text-xs text-slate-500">
          <span>Compleetheid</span>
          <span className="font-semibold">{gevuld}/{totaal} velden bekend</span>
        </div>
        <div className="h-1.5 rounded-full bg-slate-200">
          <div className={classNames("h-1.5 rounded-full transition-all", kleur)} style={{width: `${pctVal}%`}} />
        </div>
      </div>
    </div>
  );
}

function WpUitsplitsing({wp_historie}) {
  const record = wp_historie?.[0] ?? null;
  const r = record || {};
  const velden = [r.man, r.vrouw, r.voltijd, r.deeltijd, r.eigen_personeel, r.uitzend, r.detachering, r.wsw, r.pct_op_locatie];
  const gevuld = velden.filter((v) => v != null).length;

  return (
    <Panel title={record ? `WP-uitsplitsing ${record.wp_jaar}` : "WP-uitsplitsing"}>
      <Volledigheid gevuld={gevuld} totaal={velden.length} />
      {!record && (
        <div className="mb-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Nog geen goedgekeurd WP-record — uitsplitsing beschikbaar na goedkeuring of chat/belactie.
        </div>
      )}
      <div className="space-y-4 text-sm">
        <div>
          <div className="mb-2 text-xs font-semibold uppercase text-slate-400">Man / vrouw</div>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KennisVeld label="Man" value={r.man} bron="chat" />
            <KennisVeld label="Vrouw" value={r.vrouw} bron="chat" />
          </dl>
        </div>
        <div>
          <div className="mb-2 text-xs font-semibold uppercase text-slate-400">Voltijd / deeltijd</div>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KennisVeld label="Voltijd (≥12u)" value={r.voltijd} bron="chat" />
            <KennisVeld label="Deeltijd (&lt;12u)" value={r.deeltijd} bron="chat" />
            <KennisVeld label="% op locatie" value={r.pct_op_locatie != null ? Math.round(r.pct_op_locatie * 100) : null} unit="%" bron="chat" />
          </dl>
        </div>
        <div>
          <div className="mb-2 text-xs font-semibold uppercase text-slate-400">Type personeel</div>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <KennisVeld label="Eigen personeel" value={r.eigen_personeel} bron="chat" />
            <KennisVeld label="Uitzend" value={r.uitzend} bron="chat" />
            <KennisVeld label="Detachering" value={r.detachering} bron="chat" />
            <KennisVeld label="WSW" value={r.wsw} bron="chat" />
          </dl>
        </div>
      </div>
    </Panel>
  );
}

const VASTGOED_VELDEN = [
  {key: "perceel_opp",          label: "Perceeloppervlakte",       unit: "m²", type: "number"},
  {key: "winkel_opp",           label: "Winkeloppervlakte",        unit: "m²", type: "number"},
  {key: "kantoor_opp",          label: "Kantooroppervlakte",       unit: "m²", type: "number"},
  {key: "bedrijfs_opp",         label: "Bedrijfsvloeroppervlakte", unit: "m²", type: "number"},
  {key: "correspondentieadres", label: "Correspondentieadres",     unit: "",   type: "text"},
  {key: "uitbreidingsruimte",   label: "Uitbreidingsruimte",       unit: "",   type: "bool"},
  {key: "seizoensverschillen",  label: "Seizoensverschillen",      unit: "",   type: "bool"},
];

function VastgoedKaart({api, batchId, companyId, vastgoed: initVastgoed}) {
  const leeg = {perceel_opp: "", winkel_opp: "", kantoor_opp: "", bedrijfs_opp: "",
                uitbreidingsruimte: null, seizoensverschillen: null,
                seizoen_toelichting: "", correspondentieadres: ""};
  const [form, setForm] = useState(() => ({...leeg, ...(initVastgoed || {}),
    perceel_opp: initVastgoed?.perceel_opp ?? "",
    winkel_opp: initVastgoed?.winkel_opp ?? "",
    kantoor_opp: initVastgoed?.kantoor_opp ?? "",
    bedrijfs_opp: initVastgoed?.bedrijfs_opp ?? "",
  }));
  const [bewerken, setBewerken] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  function set(key, value) { setForm((p) => ({...p, [key]: value})); setSaved(false); }

  async function save() {
    setSaving(true); setError("");
    try {
      await api.saveVastgoed(batchId, companyId, {
        perceel_opp: form.perceel_opp !== "" ? Number(form.perceel_opp) : null,
        winkel_opp: form.winkel_opp !== "" ? Number(form.winkel_opp) : null,
        kantoor_opp: form.kantoor_opp !== "" ? Number(form.kantoor_opp) : null,
        bedrijfs_opp: form.bedrijfs_opp !== "" ? Number(form.bedrijfs_opp) : null,
        uitbreidingsruimte: form.uitbreidingsruimte,
        seizoensverschillen: form.seizoensverschillen,
        seizoen_toelichting: form.seizoen_toelichting || null,
        correspondentieadres: form.correspondentieadres || null,
      });
      setSaved(true); setBewerken(false);
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  const vg = initVastgoed || {};
  const gevuld = VASTGOED_VELDEN.filter(({key}) => vg[key] != null && vg[key] !== "").length;

  return (
    <Panel title="Vastgoed & locatie">
      <Volledigheid gevuld={gevuld} totaal={VASTGOED_VELDEN.length} />
      {!bewerken ? (
        <>
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
            {VASTGOED_VELDEN.map(({key, label, unit}) => (
              <KennisVeld key={key} label={label}
                value={vg[key] != null && vg[key] !== "" ? vg[key] : null}
                unit={unit} bron="chat" />
            ))}
          </dl>
          {vg.seizoensverschillen === true && vg.seizoen_toelichting && (
            <div className="mt-3 rounded-md border border-line bg-panel px-3 py-2 text-xs text-slate-600">
              <span className="font-medium">Seizoenstoelichting: </span>{vg.seizoen_toelichting}
            </div>
          )}
          {initVastgoed?.updated_at && (
            <div className="mt-2 text-xs text-slate-400">
              Bijgewerkt {new Date(initVastgoed.updated_at).toLocaleDateString("nl-NL")} · {initVastgoed.bron || "handmatig"}
            </div>
          )}
          <div className="mt-3 border-t border-line pt-3">
            <button className="text-sm font-medium text-etil underline" onClick={() => setBewerken(true)}>
              {gevuld === 0 ? "Gegevens invullen" : "Bewerken"}
            </button>
          </div>
        </>
      ) : (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            {VASTGOED_VELDEN.filter(({type}) => type !== "bool").map(({key, label, unit, type}) => (
              <div key={key}>
                <label className="mb-1 block text-xs font-medium text-slate-500">{label}{unit ? ` (${unit})` : ""}</label>
                <input className="focus-ring h-9 w-full rounded-md border border-line px-3 text-sm"
                  type={type === "number" ? "number" : "text"} min="0"
                  value={form[key] ?? ""} onChange={(e) => set(key, e.target.value)} placeholder="—" />
              </div>
            ))}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {["uitbreidingsruimte", "seizoensverschillen"].map((key) => (
              <div key={key}>
                <div className="mb-1 text-xs font-medium text-slate-500">
                  {key === "uitbreidingsruimte" ? "Uitbreidingsruimte" : "Seizoensverschillen"}
                </div>
                <div className="flex gap-3 text-sm">
                  {[true, false, null].map((v) => (
                    <label key={String(v)} className="flex cursor-pointer items-center gap-1.5">
                      <input type="radio" checked={form[key] === v} onChange={() => set(key, v)} />
                      {v === true ? "Ja" : v === false ? "Nee" : "Onbekend"}
                    </label>
                  ))}
                </div>
              </div>
            ))}
          </div>
          {form.seizoensverschillen === true && (
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-500">Toelichting seizoen</label>
              <textarea className="focus-ring min-h-16 w-full rounded-md border border-line px-3 py-2 text-sm"
                value={form.seizoen_toelichting || ""} onChange={(e) => set("seizoen_toelichting", e.target.value)}
                placeholder="Bijv. zomer +30% door terrasmedewerkers" />
            </div>
          )}
          {error && <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</div>}
          <div className="flex items-center gap-3 border-t border-line pt-3">
            <IconButton icon={Check} variant="primary" onClick={save} disabled={saving}>{saving ? "Opslaan…" : "Opslaan"}</IconButton>
            <button className="text-sm text-slate-500 underline" onClick={() => setBewerken(false)}>Annuleren</button>
            {saved && <span className="text-sm font-medium text-emerald-700"><Check size={14} className="inline" /> Opgeslagen</span>}
          </div>
        </div>
      )}
    </Panel>
  );
}

function WpHistorie({wp_historie}) {
  return (
    <Panel title="WP-historie">
      {!wp_historie?.length ? (
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <span>Nog geen goedgekeurde records</span>
          <BronTag bron="pipeline" />
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead className="text-xs uppercase text-slate-400">
              <tr>
                <th className="pb-2 pr-4">Jaar</th>
                <th className="pb-2 pr-4">WP</th>
                <th className="pb-2 pr-4">Bron</th>
                <th className="pb-2 pr-4">Status</th>
                <th className="pb-2">Goedgekeurd</th>
              </tr>
            </thead>
            <tbody>
              {wp_historie.map((r, i) => (
                <tr key={i} className="border-t border-line">
                  <td className="py-2 pr-4 font-semibold">{r.wp_jaar}</td>
                  <td className="py-2 pr-4 font-semibold text-etil">{r.wp_waarde}</td>
                  <td className="py-2 pr-4 text-slate-500">{r.bron_type || "—"}</td>
                  <td className="py-2 pr-4"><StatusPill status={r.status} /></td>
                  <td className="py-2 text-xs text-slate-400">
                    {r.goedgekeurd_op ? new Date(r.goedgekeurd_op).toLocaleDateString("nl-NL") : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function VorigJaarVergelijking({vorig_jaar, huidig_wp}) {
  if (!vorig_jaar) return null;
  const {wp_jaar, wp_waarde, verschil_abs, verschil_pct, signaal} = vorig_jaar;
  const isHoog = signaal === "hoog";
  const isPositief = verschil_abs != null && verschil_abs > 0;
  const isNegatief = verschil_abs != null && verschil_abs < 0;
  const pctTekst = verschil_pct != null
    ? `${isPositief ? "+" : ""}${(verschil_pct * (isNegatief ? -100 : 100)).toFixed(1)}%`
    : null;

  return (
    <Panel title="Vergelijking vorig jaar">
      {isHoog ? (
        <div className="mb-4 flex items-start gap-2 rounded-md border border-orange-300 bg-orange-50 p-3 text-sm text-orange-900">
          <AlertTriangle size={17} className="mt-0.5 shrink-0" />
          <div>
            <strong>Grote afwijking (&gt;25%)</strong> — controleer of dit plausibel is vóór goedkeuring.
            Groen label sluit een grote jaarfluctuatie niet uit.
          </div>
        </div>
      ) : null}
      <div className="grid grid-cols-3 gap-3 text-center">
        <div className="rounded-md border border-line bg-panel p-3">
          <div className="text-xs font-medium uppercase text-slate-500 mb-1">{wp_jaar}</div>
          <div className="text-2xl font-semibold">{wp_waarde}</div>
          <div className="text-xs text-slate-400 mt-0.5">vorig jaar</div>
        </div>
        <div className="rounded-md border border-line bg-panel p-3">
          <div className="text-xs font-medium uppercase text-slate-500 mb-1">Verschil</div>
          <div className={classNames(
            "text-2xl font-semibold",
            isPositief ? "text-emerald-700" : isNegatief ? "text-red-700" : "text-slate-500",
          )}>
            {verschil_abs != null ? (isPositief ? "+" : "") + verschil_abs : "—"}
          </div>
          {pctTekst ? <div className="text-xs text-slate-400 mt-0.5">{pctTekst}</div> : null}
        </div>
        <div className="rounded-md border border-line bg-panel p-3">
          <div className="text-xs font-medium uppercase text-slate-500 mb-1">Huidig</div>
          <div className="text-2xl font-semibold">{huidig_wp ?? "—"}</div>
          <div className="text-xs text-slate-400 mt-0.5">kandidaat</div>
        </div>
      </div>
    </Panel>
  );
}

function BatchTimestamp({created_at, completed_at}) {
  function fmt(iso) {
    if (!iso) return null;
    const d = new Date(iso);
    return d.toLocaleString("nl-NL", {day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"});
  }
  return (
    <div>
      <div>{fmt(created_at) || "-"}</div>
      {completed_at ? <div className="text-xs text-slate-400">klaar {fmt(completed_at)}</div> : null}
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

function ChatForm({token}) {
  const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
  const [session, setSession] = useState(null);
  const [answers, setAnswers] = useState({});
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/chat/${token}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.status === "completed") {
          setDone(true);
        } else {
          setSession(data);
          if (data.pre_fill_wp) {
            setAnswers((prev) => ({...prev, wp_count: String(data.pre_fill_wp)}));
          }
        }
      })
      .catch(() => setError("Chat-sessie niet gevonden of verlopen."));
  }, [token]);

  function setAnswer(id, value) {
    setAnswers((prev) => ({...prev, [id]: value}));
  }

  async function submit(e) {
    e.preventDefault();
    const vragen = session?.vragen || [];
    for (const v of vragen) {
      if (v.verplicht && !answers[v.id] && answers[v.id] !== 0) {
        setError(`Vul "${v.label}" in.`); return;
      }
    }
    const wpRaw = answers["wp_count"];
    const n = parseInt(wpRaw, 10);
    if (isNaN(n) || n < 0) { setError("Vul een geldig aantal werkzame personen in."); return; }
    setBusy(true);
    setError("");
    try {
      const r = await fetch(`${API_URL}/chat/${token}/submit`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({antwoorden: {...answers, wp_count: n}}),
      });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.detail || "Inzenden mislukt.");
      setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (error && !session) return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5] px-4">
      <div className="w-full max-w-md rounded-lg border border-red-200 bg-white p-8 text-center shadow-sm">
        <X className="mx-auto mb-3 text-red-500" size={32} />
        <p className="font-medium text-red-800">{error}</p>
      </div>
    </main>
  );

  if (done) return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5] px-4">
      <div className="w-full max-w-md rounded-lg border border-line bg-white p-8 text-center shadow-sm">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100">
          <Check className="text-emerald-600" size={28} />
        </div>
        <h2 className="mb-2 text-xl font-semibold">Bedankt!</h2>
        <p className="text-slate-600">Uw gegevens zijn ontvangen. U kunt dit venster sluiten.</p>
      </div>
    </main>
  );

  if (!session) return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5]">
      <div className="text-slate-500">Laden…</div>
    </main>
  );

  const vragen = session.vragen || [];

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5] px-4 py-8">
      <div className="w-full max-w-lg rounded-lg border border-line bg-white shadow-sm">
        <div className="rounded-t-lg bg-etil px-6 py-4">
          <div className="flex items-center gap-3">
            <ShieldCheck className="text-white/80" size={22} />
            <div>
              <div className="text-sm font-semibold text-white">Vestigingsregister AI</div>
              <div className="text-xs text-white/70">Etil Research Group — Provincie Limburg</div>
            </div>
          </div>
        </div>
        <div className="p-6">
          <h1 className="mb-1 text-xl font-semibold">Gegevenscontrole</h1>
          <p className="mb-5 text-sm text-slate-600">
            Provincie Limburg vraagt u de personeelsgegevens van{" "}
            <strong>{session.bedrijfsnaam}</strong>
            {session.gemeente ? ` (${session.gemeente})` : ""} te controleren.
          </p>
          {session.variant === "gericht" && session.pre_fill_wp ? (
            <div className="mb-5 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              Onze gegevens tonen <strong>{session.pre_fill_wp} werkzame personen</strong>.
              Klopt dit, of wilt u het corrigeren?
            </div>
          ) : null}
          <form onSubmit={submit} className="space-y-5">
            {vragen.map((vraag) => (
              <div key={vraag.id}>
                <label className="mb-1 block text-sm font-medium">
                  {vraag.label}
                  {!vraag.verplicht && <span className="ml-1 font-normal text-slate-500">(optioneel)</span>}
                </label>
                {vraag.hint ? <p className="mb-2 text-xs text-slate-500">{vraag.hint}</p> : null}
                {vraag.type === "wp_count" ? (
                  <input
                    className="focus-ring h-12 w-full rounded-md border border-line px-3 text-lg font-semibold"
                    type="number" min="0"
                    value={answers[vraag.id] ?? ""}
                    onChange={(e) => setAnswer(vraag.id, e.target.value)}
                    placeholder="bijv. 250"
                    required={vraag.verplicht}
                  />
                ) : vraag.type === "text" ? (
                  <textarea
                    className="focus-ring min-h-20 w-full rounded-md border border-line px-3 py-2 text-sm"
                    value={answers[vraag.id] ?? ""}
                    onChange={(e) => setAnswer(vraag.id, e.target.value)}
                    placeholder={vraag.hint || ""}
                    required={vraag.verplicht}
                  />
                ) : vraag.type === "boolean" ? (
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={!!answers[vraag.id]}
                      onChange={(e) => setAnswer(vraag.id, e.target.checked)}
                    />
                    {vraag.label}
                  </label>
                ) : (
                  <input
                    className="focus-ring h-10 w-full rounded-md border border-line px-3 text-sm"
                    value={answers[vraag.id] ?? ""}
                    onChange={(e) => setAnswer(vraag.id, e.target.value)}
                    required={vraag.verplicht}
                  />
                )}
              </div>
            ))}
            {error ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</div> : null}
            <button
              type="submit" disabled={busy}
              className="focus-ring flex w-full items-center justify-center gap-2 rounded-md bg-etil px-4 py-3 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
            >
              <Check size={16} />{busy ? "Bezig…" : "Gegevens bevestigen"}
            </button>
          </form>
          <p className="mt-4 text-center text-xs text-slate-400">
            Uw gegevens worden uitsluitend gebruikt voor het Vestigingsregister van Provincie Limburg.
          </p>
        </div>
      </div>
    </main>
  );
}

const CHAT_STATUS = {
  created: {label: "Verzonden", cls: "bg-blue-100 text-blue-800"},
  completed: {label: "Ingevuld", cls: "bg-amber-100 text-amber-800"},
  verwerkt: {label: "Doorvoerd", cls: "bg-emerald-100 text-emerald-800"},
};

function ChatSessiesView({api, user, onLogout, batchId, openBatch}) {
  const [sessies, setSessies] = useState([]);
  const [doorgevoerd, setDoorgevoerd] = useState({});
  const [saving, setSaving] = useState({});
  const [error, setError] = useState("");

  async function load() {
    const data = await api.chatSessies(batchId);
    setSessies(data);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    const timer = window.setInterval(() => load().catch(() => {}), 5000);
    return () => window.clearInterval(timer);
  }, [batchId]);

  async function doorvoeren(sessionId) {
    setSaving((prev) => ({...prev, [sessionId]: true}));
    try {
      await api.doorvoerenChat(sessionId);
      setDoorgevoerd((prev) => ({...prev, [sessionId]: true}));
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving((prev) => ({...prev, [sessionId]: false}));
    }
  }

  const totaal = sessies.length;
  const ingevuld = sessies.filter((s) => s.status === "completed").length;
  const verwerkt = sessies.filter((s) => s.verwerkt).length;

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title="Chat-sessies"
      actions={<IconButton icon={ListChecks} onClick={() => openBatch(batchId)}>Batchoverzicht</IconButton>}
    >
      {error ? <Alert message={error} /> : null}
      <div className="mb-4 grid gap-3 md:grid-cols-3">
        <Metric title="Totaal verzonden" value={totaal} />
        <Metric title="Ingevuld" value={ingevuld} />
        <Metric title="Doorvoerd" value={verwerkt} />
      </div>
      {!sessies.length ? (
        <div className="rounded-lg border border-line bg-white p-8 text-center text-slate-500">
          Geen chat-sessies voor deze batch
        </div>
      ) : (
        <div className="space-y-3">
          {sessies.map((s) => {
            const statusKey = s.verwerkt ? "verwerkt" : s.status;
            const cfg = CHAT_STATUS[statusKey] || CHAT_STATUS.created;
            return (
              <div key={s.id} className="rounded-lg border border-line bg-white p-4">
                <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="font-semibold">{s.naam}</div>
                    <div className="text-sm text-slate-500">{s.gemeente}</div>
                    {s.sent_at ? (
                      <div className="mt-1 text-xs text-slate-400">
                        Verzonden {new Date(s.sent_at).toLocaleString("nl-NL", {day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"})}
                      </div>
                    ) : null}
                  </div>
                  <span className={classNames("rounded-md px-2 py-1 text-xs font-semibold", cfg.cls)}>{cfg.label}</span>
                </div>
                <div className="grid gap-4 text-sm md:grid-cols-2">
                  <div>
                    <span className="text-xs font-medium uppercase text-slate-500">Pipeline-schatting</span>
                    <div className="mt-1 text-lg font-semibold">{s.wp_kandidaat ?? "-"} WP</div>
                  </div>
                  {s.status === "completed" || s.verwerkt ? (
                    <div>
                      <span className="text-xs font-medium uppercase text-slate-500">Opgegeven door bedrijf</span>
                      <div className="mt-1 text-lg font-semibold text-etil">{s.wp_opgegeven ?? "-"} WP</div>
                    </div>
                  ) : null}
                </div>
                {s.antwoorden && Object.keys(s.antwoorden).length > 0 && (
                  <div className="mt-3 rounded-md border border-line bg-panel p-3 text-sm">
                    <div className="mb-2 text-xs font-medium uppercase text-slate-500">Antwoorden</div>
                    {Object.entries(s.antwoorden).map(([k, v]) => (
                      <div key={k} className="flex gap-3">
                        <span className="text-slate-500 min-w-24">{k}</span>
                        <span className="font-medium">{String(v || "-")}</span>
                      </div>
                    ))}
                  </div>
                )}
                {s.completed_at ? (
                  <div className="mt-3 flex items-center justify-between border-t border-line pt-3">
                    <span className="text-sm text-slate-500">
                      Ingevuld op {new Date(s.completed_at).toLocaleString("nl-NL", {day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit"})}
                    </span>
                    {s.verwerkt || doorgevoerd[s.id] ? (
                      <span className="inline-flex items-center gap-1 text-sm font-medium text-emerald-700">
                        <Check size={15} /> Doorvoerd
                      </span>
                    ) : (
                      <IconButton
                        icon={Check}
                        variant="primary"
                        onClick={() => doorvoeren(s.id)}
                        disabled={saving[s.id]}
                      >
                        {saving[s.id] ? "…" : "Doorvoeren"}
                      </IconButton>
                    )}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </Shell>
  );
}

const VRAAG_TYPES = [
  {value: "wp_count", label: "WP-getal"},
  {value: "text", label: "Tekstveld"},
  {value: "boolean", label: "Ja/Nee"},
  {value: "number", label: "Getal"},
];

function ChatTemplatesView({api, user, onLogout, openDashboard}) {
  const [templates, setTemplates] = useState([]);
  const [selected, setSelected] = useState(null); // {id?, naam, beschrijving, vragen, is_default}
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function load() {
    const data = await api.chatTemplates();
    setTemplates(data);
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  function newTemplate() {
    setSelected({
      naam: "Nieuw template",
      beschrijving: "",
      vragen: [
        {id: "wp_count", label: "Aantal werkzame personen", type: "wp_count", verplicht: true, hint: "Headcount (niet FTE)"},
        {id: "opmerking", label: "Toelichting", type: "text", verplicht: false, hint: ""},
      ],
      is_default: false,
    });
    setSaved(false);
    setError("");
  }

  function editTemplate(t) {
    setSelected({...t, vragen: t.vragen ? [...t.vragen.map((v) => ({...v}))] : []});
    setSaved(false);
    setError("");
  }

  async function deleteTemplate(t) {
    if (!window.confirm(`Template "${t.naam}" verwijderen?`)) return;
    setDeleting(t.id);
    try {
      await api.deleteTemplate(t.id);
      if (selected?.id === t.id) setSelected(null);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleting(null);
    }
  }

  async function save() {
    if (!selected) return;
    setSaving(true);
    setError("");
    try {
      if (selected.id) {
        await api.updateTemplate(selected.id, {naam: selected.naam, beschrijving: selected.beschrijving, vragen: selected.vragen, is_default: selected.is_default});
      } else {
        const result = await api.createTemplate({naam: selected.naam, beschrijving: selected.beschrijving, vragen: selected.vragen, is_default: selected.is_default});
        setSelected((prev) => ({...prev, id: result.id}));
      }
      await load();
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  function setField(field, value) {
    setSelected((prev) => ({...prev, [field]: value}));
    setSaved(false);
  }

  function setVraagField(index, field, value) {
    setSelected((prev) => {
      const vragen = [...prev.vragen];
      vragen[index] = {...vragen[index], [field]: value};
      return {...prev, vragen};
    });
    setSaved(false);
  }

  function addVraag() {
    const newId = `vraag_${Date.now()}`;
    setSelected((prev) => ({
      ...prev,
      vragen: [...prev.vragen, {id: newId, label: "Nieuwe vraag", type: "text", verplicht: false, hint: ""}],
    }));
    setSaved(false);
  }

  function removeVraag(index) {
    setSelected((prev) => ({
      ...prev,
      vragen: prev.vragen.filter((_, i) => i !== index),
    }));
    setSaved(false);
  }

  function moveVraag(index, dir) {
    const newIndex = index + dir;
    if (newIndex < 0 || !selected || newIndex >= selected.vragen.length) return;
    setSelected((prev) => {
      const vragen = [...prev.vragen];
      [vragen[index], vragen[newIndex]] = [vragen[newIndex], vragen[index]];
      return {...prev, vragen};
    });
    setSaved(false);
  }

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title="Chat-templates"
      actions={
        <>
          <IconButton icon={ListChecks} onClick={openDashboard}>Dashboard</IconButton>
          <IconButton icon={Plus} variant="primary" onClick={newTemplate}>Nieuw template</IconButton>
        </>
      }
    >
      {error ? <Alert message={error} /> : null}
      <div className="grid gap-5 lg:grid-cols-[320px_1fr]">
        {/* Template-lijst */}
        <div className="space-y-2">
          {!templates.length ? (
            <div className="rounded-lg border border-line bg-white p-6 text-center text-sm text-slate-500">
              Geen templates — maak er een aan.
            </div>
          ) : templates.map((t) => (
            <div
              key={t.id}
              className={classNames(
                "cursor-pointer rounded-lg border bg-white p-4 transition",
                selected?.id === t.id ? "border-etil ring-1 ring-etil" : "border-line hover:bg-panel",
              )}
              onClick={() => editTemplate(t)}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-semibold text-sm">{t.naam}</div>
                  {t.beschrijving ? <div className="mt-0.5 text-xs text-slate-500 line-clamp-1">{t.beschrijving}</div> : null}
                  <div className="mt-1 text-xs text-slate-400">{(t.vragen || []).length} vragen</div>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  {t.is_default ? (
                    <span className="rounded bg-etil/10 px-1.5 py-0.5 text-xs font-semibold text-etil">Standaard</span>
                  ) : null}
                  <button
                    className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
                    onClick={(e) => { e.stopPropagation(); deleteTemplate(t); }}
                    disabled={deleting === t.id || t.is_default}
                    title={t.is_default ? "Standaard-template kan niet worden verwijderd" : "Verwijderen"}
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Editor */}
        {selected ? (
          <div className="rounded-lg border border-line bg-white p-5">
            <div className="mb-5 grid gap-4">
              <div>
                <label className="mb-1 block text-sm font-medium">Naam</label>
                <input
                  className="focus-ring h-10 w-full rounded-md border border-line px-3"
                  value={selected.naam}
                  onChange={(e) => setField("naam", e.target.value)}
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium">Beschrijving</label>
                <input
                  className="focus-ring h-10 w-full rounded-md border border-line px-3 text-sm"
                  value={selected.beschrijving || ""}
                  onChange={(e) => setField("beschrijving", e.target.value)}
                  placeholder="Optionele omschrijving"
                />
              </div>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={selected.is_default}
                  onChange={(e) => setField("is_default", e.target.checked)}
                />
                <span>Standaard-template (wordt automatisch gebruikt bij nieuwe uitnodigingen)</span>
              </label>
            </div>

            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold">Vragen</h3>
              <button
                className="inline-flex items-center gap-1 rounded-md border border-etil px-2 py-1 text-xs font-medium text-etil hover:bg-etil/5"
                onClick={addVraag}
              >
                <Plus size={13} /> Vraag toevoegen
              </button>
            </div>

            <div className="mb-5 space-y-2">
              {(selected.vragen || []).map((vraag, i) => (
                <div key={vraag.id || i} className="rounded-md border border-line bg-panel p-3">
                  <div className="mb-2 flex items-center gap-2">
                    <GripVertical size={15} className="shrink-0 text-slate-400" />
                    <div className="grid flex-1 gap-2 sm:grid-cols-[1fr_140px_80px]">
                      <input
                        className="focus-ring h-8 rounded-md border border-line bg-white px-2 text-sm"
                        value={vraag.label}
                        onChange={(e) => setVraagField(i, "label", e.target.value)}
                        placeholder="Label"
                      />
                      <select
                        className="focus-ring h-8 rounded-md border border-line bg-white px-2 text-sm"
                        value={vraag.type}
                        onChange={(e) => setVraagField(i, "type", e.target.value)}
                      >
                        {VRAAG_TYPES.map(({value, label}) => <option key={value} value={value}>{label}</option>)}
                      </select>
                      <label className="flex h-8 items-center gap-1 text-xs text-slate-600">
                        <input
                          type="checkbox"
                          checked={vraag.verplicht}
                          onChange={(e) => setVraagField(i, "verplicht", e.target.checked)}
                        />
                        Verplicht
                      </label>
                    </div>
                    <div className="flex shrink-0 gap-1">
                      <button className="rounded p-1 text-slate-400 hover:bg-white hover:text-slate-700" onClick={() => moveVraag(i, -1)} disabled={i === 0}><ChevronUp size={14} /></button>
                      <button className="rounded p-1 text-slate-400 hover:bg-white hover:text-slate-700" onClick={() => moveVraag(i, 1)} disabled={i === selected.vragen.length - 1}><ChevronDown size={14} /></button>
                      <button className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600" onClick={() => removeVraag(i)}><Trash2 size={14} /></button>
                    </div>
                  </div>
                  <input
                    className="focus-ring h-8 w-full rounded-md border border-line bg-white px-2 text-xs text-slate-600"
                    value={vraag.hint || ""}
                    onChange={(e) => setVraagField(i, "hint", e.target.value)}
                    placeholder="Hint / toelichting (zichtbaar voor bedrijf)"
                  />
                </div>
              ))}
              {!selected.vragen?.length ? (
                <div className="rounded-md border border-dashed border-line p-4 text-center text-sm text-slate-400">
                  Nog geen vragen — klik op "Vraag toevoegen"
                </div>
              ) : null}
            </div>

            <div className="flex items-center gap-3 border-t border-line pt-4">
              <IconButton icon={Check} variant="primary" onClick={save} disabled={saving}>
                {saving ? "Opslaan…" : "Opslaan"}
              </IconButton>
              {saved ? <span className="text-sm font-medium text-emerald-700"><Check size={14} className="inline" /> Opgeslagen</span> : null}
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-line bg-white p-8 text-center text-sm text-slate-400">
            Selecteer een template om te bewerken, of maak een nieuw template aan.
          </div>
        )}
      </div>
    </Shell>
  );
}

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
    />
  );
}
