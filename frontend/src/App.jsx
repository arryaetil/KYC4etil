import {useEffect, useMemo, useRef, useState} from "react";
import {
  AlertTriangle,
  BookOpen,
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
  Pencil,
  Phone,
  Play,
  Plus,
  RefreshCw,
  Search,
  Send,
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
    primary: "border-etil bg-etil text-white hover:opacity-90",
    danger: "border-red-600 bg-red-600 text-white hover:bg-red-700",
    quiet: "border-transparent bg-transparent text-slate-600 hover:bg-panel",
    danger: "border-red-200 bg-red-50 text-red-600 hover:bg-red-100",
    ghost: "border-transparent bg-transparent text-white hover:bg-white/10",
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

function Shell({user, onLogout, children, title, actions}) {
  return (
    <div className="min-h-screen bg-[#eef2f5]">
      <header className="bg-[#C8102E]">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-4">
            <div className="flex flex-col leading-none">
              <span className="text-2xl font-black italic text-white tracking-tight">Etil</span>
              <span className="text-[10px] font-medium text-white/70 tracking-wide">research group</span>
            </div>
            {title && <><div className="h-8 w-px bg-white/20" /><h1 className="text-xl font-semibold text-white">{title}</h1></>}
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden text-right text-sm sm:block">
              <div className="font-medium text-white">{user?.naam}</div>
              <div className="text-white/60">{user?.rol}</div>
            </div>
            <IconButton icon={LogOut} variant="ghost" onClick={onLogout} title="Uitloggen" />
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

function Dashboard({api, user, onLogout, openBatch, openChatTemplates, openJaarverslagen}) {
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
      title=""
      actions={
        <>
          <input ref={fileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={upload} />
          <IconButton icon={BookOpen} variant="quiet" onClick={openJaarverslagen}>Jaarverslagen</IconButton>
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
              <th className="w-36 px-4 py-3">Voortgang</th>
              <th className="w-48 px-4 py-3">Labels</th>
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
    const text = `${company.naam || ""} ${company.gemeente || ""}`.toLowerCase();
    return text.includes(search.toLowerCase());
  }), [companies, label, search]);

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
          <IconButton icon={FileDown} onClick={() => api.download(`/batches/${batchId}/export.xlsx`, "export.xlsx")}>Export</IconButton>
          <IconButton icon={Phone} onClick={() => openBellijst(batchId)}>Bellijst</IconButton>
          <div className="relative inline-flex">
            <IconButton icon={MessageSquare} onClick={() => openChatSessies(batchId)}>Chat-sessies</IconButton>
            {batch?.chat_sessies_open > 0 && (
              <span className="pointer-events-none absolute -right-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-500 px-1 text-xs font-bold text-white">
                {batch.chat_sessies_open}
              </span>
            )}
          </div>
          <IconButton icon={Trash2} variant="quiet" onClick={deleteBatch} disabled={busy || isRunning} title="Batch verwijderen" />
        </>
      }
    >
      {error ? <Alert message={error} /> : null}
      <div className="mb-4 grid gap-3 md:grid-cols-[1fr_200px]">
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

  async function verwijder(id, naam) {
    if (!window.confirm(`"${naam}" van de bellijst verwijderen?`)) return;
    setSaving((prev) => ({...prev, [`del_${id}`]: true}));
    try {
      await api.deleteBellijstItem(id);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving((prev) => ({...prev, [`del_${id}`]: false}));
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
          <IconButton icon={Download} onClick={() => api.download(`/batches/${batchId}/bellijst.xlsx`, "bellijst.xlsx")}>Exporteren</IconButton>
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
                  <div className="flex items-end gap-2">
                    <IconButton
                      icon={Check}
                      variant="primary"
                      className="flex-1 justify-center"
                      onClick={() => save(item.id)}
                      disabled={saving[item.id]}
                    >
                      {saving[item.id] ? "…" : "Opslaan"}
                    </IconButton>
                    <IconButton
                      icon={Trash2}
                      variant="danger"
                      onClick={() => verwijder(item.id, item.naam)}
                      disabled={saving[`del_${item.id}`]}
                      title="Verwijder van bellijst"
                    />
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

function WpKaart({candidate, wp_historie, vorig_jaar, api, onRefresh}) {
  const [editMode, setEditMode] = useState(false);
  const [correctWp, setCorrectWp] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function bevestigen() {
    if (!candidate) return;
    setBusy(true); setError("");
    try {
      if (correctWp && Number(correctWp) !== candidate.wp_kandidaat) {
        await api.correct(candidate.id, correctWp, reason);
      } else {
        await api.approve(candidate.id);
      }
      setEditMode(false); setCorrectWp(""); setReason("");
      await onRefresh();
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  const isHoog = vorig_jaar?.signaal === "hoog";
  const recentHistorie = wp_historie?.slice(0, 4) || [];

  return (
    <Panel
      title="Werkzame personen"
      collapsible
      defaultOpen
      onEdit={candidate ? () => setEditMode((e) => !e) : undefined}
    >
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          {editMode ? (
            <input
              className="focus-ring h-12 w-32 rounded-md border border-line px-3 text-2xl font-bold"
              type="number" min="0"
              value={correctWp}
              onChange={(e) => setCorrectWp(e.target.value)}
              placeholder={String(candidate?.wp_kandidaat ?? "")}
              autoFocus
            />
          ) : (
            <div className="text-4xl font-bold text-ink">{candidate?.wp_kandidaat ?? "—"}</div>
          )}
          <div className="mt-0.5 text-xs text-slate-400">gevonden door agent</div>
        </div>
        <LabelBadge label={candidate?.confidence_label} />
      </div>
      <Progress value={pct(candidate?.confidence_score)} total={100} />
      {candidate?.is_schatting && (
        <div className="mt-3 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-900">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          Proportionele schatting — niet geschikt voor groen label.
        </div>
      )}
      {isHoog && (
        <div className="mt-3 flex items-start gap-2 rounded-md border border-orange-300 bg-orange-50 p-2.5 text-xs text-orange-900">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span><strong>&gt;25% afwijking</strong> t.o.v. vorig jaar — controleer voor bevestiging.</span>
        </div>
      )}
      <div className="mt-3 border-t border-line pt-3 text-xs text-slate-500">
        <span className="font-medium text-slate-700">Reconciliatie: </span>
        {candidate?.reconciliatie_reden || "—"}
      </div>
      {editMode && (
        <textarea
          className="focus-ring mt-3 min-h-16 w-full rounded-md border border-line px-3 py-2 text-sm"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="Reden voor correctie (optioneel)"
        />
      )}
      {error && <div className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{error}</div>}
      {candidate && (
        <div className="mt-4 border-t border-line pt-3">
          <IconButton icon={Check} variant="primary" className="w-full justify-center" onClick={bevestigen} disabled={busy || !candidate.wp_kandidaat}>
            {busy ? "Bezig…" : editMode && correctWp ? "Corrigeren & bevestigen" : "Bevestigen"}
          </IconButton>
          {editMode && (
            <button className="mt-2 w-full text-center text-xs text-slate-500 underline" onClick={() => { setEditMode(false); setCorrectWp(""); setReason(""); }}>
              Annuleren
            </button>
          )}
        </div>
      )}
      {recentHistorie.length > 0 && (
        <div className="mt-4 border-t border-line pt-3">
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Historie</div>
          <div className="space-y-2">
            {recentHistorie.map((r, i) => (
              <div key={i} className="flex items-center justify-between text-sm">
                <span className="text-slate-500">{r.wp_jaar}</span>
                <div className="flex items-center gap-2">
                  <span className="font-semibold">{r.wp_waarde}</span>
                  <StatusPill status={r.status} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
}

function OutboundPanel({candidate, api, batchId, companyId, onRefresh}) {
  const [chatBusy, setChatBusy] = useState(false);
  const [chatResult, setChatResult] = useState(null);
  const [belBusy, setBelBusy] = useState(false);
  const [herBusy, setHerBusy] = useState(false);
  const [error, setError] = useState("");

  async function stuurChat() {
    setChatBusy(true); setError("");
    try {
      const res = await api.createChatSession(candidate.id);
      setChatResult({ok: res.email_sent, recipient: res.email_recipient, chatUrl: res.chat_url});
      await onRefresh();
    } catch (err) { setError(err.message); }
    finally { setChatBusy(false); }
  }

  async function opBellijst() {
    setBelBusy(true); setError("");
    try { await api.bellijst(candidate.id, ""); await onRefresh(); }
    catch (err) { setError(err.message); }
    finally { setBelBusy(false); }
  }

  async function herverwerk() {
    setHerBusy(true); setError("");
    try { await api.herverwerk(batchId, companyId); await onRefresh(); }
    catch (err) { setError(err.message); }
    finally { setHerBusy(false); }
  }

  return (
    <Panel title="Outbound" collapsible>
      {error && <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{error}</div>}
      <div className="space-y-3">
        {chatResult ? (
          <div className="space-y-2">
            {chatResult.ok && (
              <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                <strong>Email verstuurd</strong> naar {chatResult.recipient}
              </div>
            )}
            {(() => {
              const token = new URL(chatResult.chatUrl, window.location.origin).searchParams.get("chat") || chatResult.chatUrl;
              const publicUrl = `${window.location.origin}/?chat=${token}`;
              return (
                <div className="rounded-md border border-line bg-panel p-3">
                  <div className="mb-1 text-xs font-medium text-slate-500">Chat-link</div>
                  <p className="mb-2 break-all text-xs text-slate-500">{publicUrl}</p>
                  <div className="flex gap-2">
                    <button className="focus-ring flex-1 rounded-md bg-etil px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90"
                      onClick={() => { window.open(`/?chat=${token}`, '_blank'); }}>
                      Open chat
                    </button>
                    <button className="focus-ring rounded-md border border-line bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-panel"
                      onClick={() => navigator.clipboard.writeText(publicUrl)}>
                      Kopieer link
                    </button>
                  </div>
                </div>
              );
            })()}
          </div>
        ) : (
          <IconButton icon={Mail} className="w-full justify-center" disabled={!candidate || chatBusy} onClick={stuurChat}>
            {chatBusy ? "Bezig…" : "Chat-uitnodiging versturen"}
          </IconButton>
        )}
        <IconButton icon={Phone} className="w-full justify-center" disabled={!candidate || belBusy} onClick={opBellijst}>
          {belBusy ? "Bezig…" : "Op bellijst zetten"}
        </IconButton>
        <div className="border-t border-line pt-3">
          <IconButton icon={RefreshCw} className="w-full justify-center" disabled={herBusy} onClick={herverwerk}>
            {herBusy ? "Bezig…" : "Herverwerk"}
          </IconButton>
        </div>
      </div>
    </Panel>
  );
}

function DetailView({api, user, onLogout, batchId, companyId, openBatch}) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState("");

  async function load() {
    setDetail(await api.company(batchId, companyId));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, [batchId, companyId]);

  const candidate = detail?.candidate;

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title={detail?.company?.naam || "Vestiging"}
      actions={<IconButton icon={ListChecks} onClick={() => openBatch(batchId)}>Batchoverzicht</IconButton>}
    >
      {error ? <Alert message={error} /> : null}
      {detail ? (
        <div className="grid gap-5 lg:grid-cols-[2fr_1fr]">
          <section className="space-y-5">
            <VestigingsgegevensKaart
              company={detail.company}
              enrichment={detail.enrichment}
              api={api}
              batchId={batchId}
              onRefresh={load}
            />
            <ContactgegevensKaart
              enrichment={detail.enrichment}
              vastgoed={detail?.vastgoed}
              api={api}
              batchId={batchId}
              companyId={companyId}
              onRefresh={load}
            />
            <WpUitsplitsing wp_historie={detail?.wp_historie} api={api} batchId={batchId} companyId={companyId} onRefresh={load} />
            <VastgoedKaart api={api} batchId={batchId} companyId={companyId} vastgoed={detail?.vastgoed} />
            <Panel title="Gevonden bronnen" collapsible defaultOpen={false}>
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
            <Panel title="Score-uitleg" collapsible defaultOpen={false}>
              <ScoreBreakdown breakdown={candidate?.score_breakdown} label={candidate?.confidence_label} />
            </Panel>
            <VorigJaarVergelijking vorig_jaar={detail?.vorig_jaar} huidig_wp={candidate?.wp_kandidaat} collapsible />
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
            <WpKaart
              candidate={candidate}
              wp_historie={detail?.wp_historie}
              vorig_jaar={detail?.vorig_jaar}
              api={api}
              onRefresh={load}
            />
            <OutboundPanel
              candidate={candidate}
              api={api}
              batchId={batchId}
              companyId={companyId}
              onRefresh={load}
            />
          </aside>
        </div>
      ) : null}
    </Shell>
  );
}

function Panel({title, subtitle, children, onEdit, completeness, collapsible = false, defaultOpen}) {
  const [open, setOpen] = useState(defaultOpen !== undefined ? defaultOpen : !collapsible);
  return (
    <section className="rounded-lg border border-line bg-white shadow-sm">
      <div
        className={classNames("flex items-center justify-between px-5 py-3", (!collapsible || open) && "border-b border-line")}
        style={collapsible ? {cursor: "pointer"} : undefined}
        onClick={collapsible ? () => setOpen((o) => !o) : undefined}
      >
        <div>
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-400">{subtitle}</p>}
        </div>
        <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
          {completeness && (
            <span className="text-xs tabular-nums text-slate-400">{completeness.gevuld}/{completeness.totaal}</span>
          )}
          {onEdit && open && (
            <button
              onClick={onEdit}
              className="rounded-md p-1.5 text-slate-400 transition hover:bg-panel hover:text-ink"
              title="Bewerken"
            >
              <Pencil size={14} />
            </button>
          )}
          {collapsible && (
            <button className="rounded-md p-1.5 text-slate-400 transition hover:bg-panel hover:text-ink" onClick={() => setOpen((o) => !o)}>
              {open ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          )}
        </div>
      </div>
      {open && <div className="px-5 py-4">{children}</div>}
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

function Tooltip({content, children}) {
  return (
    <span className="group relative inline-block">
      {children}
      <span className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-2 hidden w-max max-w-52 -translate-x-1/2 rounded-md bg-ink px-2.5 py-1.5 text-center text-xs leading-snug text-white shadow-lg group-hover:block">
        {content}
        <span className="absolute left-1/2 top-full -translate-x-1/2 border-4 border-transparent border-t-ink" />
      </span>
    </span>
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

function KennisVeld({label, value, unit, type, tooltip}) {
  const isEmpty = value === null || value === undefined || value === "";

  function renderValue() {
    if (isEmpty) return <span className="text-slate-300">—</span>;
    if (type === "link") {
      const display = String(value).replace(/^https?:\/\//, "").replace(/\/$/, "");
      return <a href={value} target="_blank" rel="noreferrer" className="break-all font-semibold text-etil underline">{display}</a>;
    }
    if (type === "email") {
      return <a href={`mailto:${value}`} className="font-semibold text-etil underline">{value}</a>;
    }
    const text = unit
      ? `${value} ${unit}`
      : String(value === true ? "Ja" : value === false ? "Nee" : value);
    return <span className="font-semibold text-ink">{text}</span>;
  }

  const labelEl = tooltip ? (
    <Tooltip content={tooltip}>
      <span className="cursor-help border-b border-dotted border-slate-300">{label}</span>
    </Tooltip>
  ) : label;

  return (
    <div>
      <dt className="mb-0.5 text-xs font-medium uppercase tracking-wide text-slate-400">{labelEl}</dt>
      <dd className="mt-0.5">{renderValue()}</dd>
    </div>
  );
}

const WP_SPLITS_VELDEN = [
  {key: "man",             label: "Man",             groep: "Geslacht"},
  {key: "vrouw",           label: "Vrouw",           groep: "Geslacht"},
  {key: "voltijd",         label: "Voltijd",         groep: "Dienstverband", tooltip: "Werkzaam ≥12 uur/week"},
  {key: "deeltijd",        label: "Deeltijd",        groep: "Dienstverband", tooltip: "Werkzaam <12 uur/week"},
  {key: "eigen_personeel", label: "Eigen personeel", groep: "Type personeel", tooltip: "Direct in dienst"},
  {key: "uitzend",         label: "Uitzend",         groep: "Type personeel", tooltip: "Ingehuurd via uitzendbureau"},
  {key: "detachering",     label: "Detachering",     groep: "Type personeel", tooltip: "Uitgeleend aan andere werkgever"},
  {key: "wsw",             label: "WSW",             groep: "Type personeel", tooltip: "Wet sociale werkvoorziening"},
];

function VestigingsgegevensKaart({company, enrichment, api, batchId, onRefresh}) {
  const c = company || {};
  const e = enrichment || {};
  const [bewerken, setBewerken] = useState(false);
  const [form, setForm] = useState({
    naam: c.naam || "", gemeente: c.gemeente || "", adres: c.adres || "",
    sbi_code: c.sbi_code || "", cb_er: c.cb_er || "", kvk_nummer: c.kvk_nummer || "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function set(key, val) { setForm((p) => ({...p, [key]: val})); }

  async function save() {
    setSaving(true); setError("");
    try {
      await api.updateCompany(batchId, c.id, Object.fromEntries(
        Object.entries(form).map(([k, v]) => [k, v || null])
      ));
      setBewerken(false);
      await onRefresh();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  return (
    <Panel title="Vestigingsgegevens" collapsible defaultOpen onEdit={() => setBewerken((b) => !b)}>
      {!bewerken ? (
        <>
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <Info label="Naam" value={c.naam} />
            <Info label="Gemeente" value={c.gemeente} />
            <Info label="Adres" value={c.adres} />
            <Info label="SBI" value={c.sbi_code} />
            <Info label="CB-er" value={c.cb_er || "—"} />
            <Info label="KvK" value={c.kvk_nummer || "—"} />
            {e.locatie_count_nl != null && (
              <Info label="Vestigingen" value={`${e.locatie_count_lb ?? "?"} in LB / ${e.locatie_count_nl} NL`} />
            )}
          </dl>
        </>
      ) : (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              {key: "naam",        label: "Naam"},
              {key: "gemeente",    label: "Gemeente"},
              {key: "adres",       label: "Adres"},
              {key: "sbi_code",    label: "SBI-code"},
              {key: "cb_er",       label: "CB-er"},
              {key: "kvk_nummer",  label: "KvK-nummer"},
            ].map(({key, label}) => (
              <div key={key}>
                <label className="mb-1 block text-xs font-medium text-slate-500">{label}</label>
                <input
                  className="focus-ring h-9 w-full rounded-md border border-line px-3 text-sm"
                  value={form[key]}
                  onChange={(e) => set(key, e.target.value)}
                  placeholder="—"
                />
              </div>
            ))}
          </div>
          {error && <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{error}</div>}
          <div className="flex items-center gap-3 border-t border-line pt-3">
            <IconButton icon={Check} variant="primary" onClick={save} disabled={saving}>{saving ? "Opslaan…" : "Opslaan"}</IconButton>
            <button className="text-sm text-slate-500 underline" onClick={() => setBewerken(false)}>Annuleren</button>
          </div>
        </div>
      )}
    </Panel>
  );
}

function WpUitsplitsing({wp_historie, api, batchId, companyId, onRefresh}) {
  const record = wp_historie?.[0] ?? null;
  const r = record || {};
  const velden = WP_SPLITS_VELDEN.map(({key}) => r[key]);
  const gevuld = [...velden, r.pct_op_locatie].filter((v) => v != null).length;

  const leeg = Object.fromEntries(WP_SPLITS_VELDEN.map(({key}) => [key, r[key] ?? ""]));
  const [bewerken, setBewerken] = useState(false);
  const [form, setForm] = useState({...leeg, pct_op_locatie: r.pct_op_locatie != null ? Math.round(r.pct_op_locatie * 100) : ""});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function set(key, val) { setForm((p) => ({...p, [key]: val})); }

  async function save() {
    setSaving(true); setError("");
    try {
      const body = Object.fromEntries(
        WP_SPLITS_VELDEN.map(({key}) => [key, form[key] !== "" ? Number(form[key]) : null])
      );
      body.pct_op_locatie = form.pct_op_locatie !== "" ? Number(form.pct_op_locatie) / 100 : null;
      await api.saveWpUitsplitsing(batchId, companyId, body);
      setBewerken(false);
      await onRefresh();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  const groepen = [...new Set(WP_SPLITS_VELDEN.map((v) => v.groep))];

  return (
    <Panel
      title="WP-uitsplitsing"
      subtitle={record ? `Peiljaar ${record.wp_jaar}` : null}
      completeness={{gevuld, totaal: velden.length + 1}}
      collapsible
      onEdit={() => setBewerken((b) => !b)}
    >
      {!record && (
        <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          Nog geen WP-record — bevestig eerst een WP-waarde in de Werkzame personen-kaart.
        </div>
      )}
      {record && (
        <div className="mb-5 flex items-baseline gap-2">
          <span className="text-3xl font-bold text-ink">{record.wp_waarde}</span>
          <span className="text-sm text-slate-500">werkzame personen</span>
        </div>
      )}
      {!bewerken ? (
        <div className="space-y-5 text-sm">
          {groepen.map((groep) => (
            <div key={groep}>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{groep}</div>
              <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                {WP_SPLITS_VELDEN.filter((v) => v.groep === groep).map(({key, label, tooltip}) => (
                  <KennisVeld key={key} label={label} value={r[key]} tooltip={tooltip} />
                ))}
                {groep === "Dienstverband" && (
                  <KennisVeld label="% op locatie" value={r.pct_op_locatie != null ? Math.round(r.pct_op_locatie * 100) : null} unit="%" tooltip="Aandeel WP werkzaam op dit vestigingsadres" />
                )}
              </dl>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-4 text-sm">
          {groepen.map((groep) => (
            <div key={groep}>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{groep}</div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {WP_SPLITS_VELDEN.filter((v) => v.groep === groep).map(({key, label}) => (
                  <div key={key}>
                    <label className="mb-1 block text-xs font-medium text-slate-500">{label}</label>
                    <input className="focus-ring h-9 w-full rounded-md border border-line px-3 text-sm" type="number" min="0"
                      value={form[key]} onChange={(e) => set(key, e.target.value)} placeholder="—" />
                  </div>
                ))}
                {groep === "Dienstverband" && (
                  <div>
                    <label className="mb-1 block text-xs font-medium text-slate-500">% op locatie</label>
                    <input className="focus-ring h-9 w-full rounded-md border border-line px-3 text-sm" type="number" min="0" max="100"
                      value={form.pct_op_locatie} onChange={(e) => set("pct_op_locatie", e.target.value)} placeholder="—" />
                  </div>
                )}
              </div>
            </div>
          ))}
          {error && <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-800">{error}</div>}
          <div className="flex items-center gap-3 border-t border-line pt-3">
            <IconButton icon={Check} variant="primary" onClick={save} disabled={saving}>{saving ? "Opslaan…" : "Opslaan"}</IconButton>
            <button className="text-sm text-slate-500 underline" onClick={() => setBewerken(false)}>Annuleren</button>
          </div>
        </div>
      )}
    </Panel>
  );
}

const VASTGOED_VELDEN = [
  {key: "perceel_opp",         label: "Perceeloppervlakte",  unit: "m²", type: "number"},
  {key: "winkel_opp",          label: "Winkeloppervlakte",   unit: "m²", type: "number"},
  {key: "kantoor_opp",         label: "Kantooroppervlakte",  unit: "m²", type: "number"},
  {key: "bedrijfs_opp",        label: "Bedrijfsvloer",       unit: "m²", type: "number"},
  {key: "uitbreidingsruimte",  label: "Uitbreiding mogelijk",unit: "",   type: "bool"},
  {key: "seizoensverschillen", label: "Seizoensverschillen", unit: "",   type: "bool"},
];

function VastgoedKaart({api, batchId, companyId, vastgoed: initVastgoed}) {
  const leeg = {perceel_opp: "", winkel_opp: "", kantoor_opp: "", bedrijfs_opp: "",
                uitbreidingsruimte: null, seizoensverschillen: null, seizoen_toelichting: ""};
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
        correspondentieadres: initVastgoed?.correspondentieadres ?? null,
      });
      setSaved(true); setBewerken(false);
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  const vg = initVastgoed || {};
  const gevuld = VASTGOED_VELDEN.filter(({key}) => vg[key] != null && vg[key] !== "").length;

  return (
    <Panel
      title="Vastgoed & locatie"
      collapsible
      onEdit={() => setBewerken((b) => !b)}
      completeness={{gevuld, totaal: VASTGOED_VELDEN.length}}
    >
      {!bewerken ? (
        <>
          <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
            {VASTGOED_VELDEN.map(({key, label, unit, type}) => (
              <KennisVeld
                key={key}
                label={label}
                value={vg[key] != null && vg[key] !== "" ? vg[key] : null}
                unit={type !== "bool" ? unit : ""}
                tooltip={key === "uitbreidingsruimte" ? "Is er ruimte voor uitbreiding op het perceel?" : key === "seizoensverschillen" ? "Fluctueert het aantal WP sterk per seizoen?" : undefined}
              />
            ))}
          </dl>
          {vg.seizoensverschillen === true && vg.seizoen_toelichting && (
            <div className="mt-3 rounded-md border border-line bg-panel px-3 py-2 text-xs text-slate-600">
              <span className="font-medium">Seizoenstoelichting: </span>{vg.seizoen_toelichting}
            </div>
          )}
          {initVastgoed?.updated_at && (
            <p className="mt-3 text-xs text-slate-400">
              Bijgewerkt {new Date(initVastgoed.updated_at).toLocaleDateString("nl-NL")} · {initVastgoed.bron || "handmatig"}
            </p>
          )}
        </>
      ) : (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            {VASTGOED_VELDEN.filter(({type}) => type !== "bool").map(({key, label, unit}) => (
              <div key={key}>
                <label className="mb-1 block text-xs font-medium text-slate-500">{label} ({unit})</label>
                <input
                  className="focus-ring h-9 w-full rounded-md border border-line px-3 text-sm"
                  type="number" min="0"
                  value={form[key] ?? ""} onChange={(e) => set(key, e.target.value)} placeholder="—"
                />
              </div>
            ))}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {["uitbreidingsruimte", "seizoensverschillen"].map((key) => (
              <div key={key}>
                <div className="mb-1 text-xs font-medium text-slate-500">
                  {key === "uitbreidingsruimte" ? "Uitbreiding mogelijk" : "Seizoensverschillen"}
                </div>
                <div className="flex gap-4 text-sm">
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
              <textarea
                className="focus-ring min-h-16 w-full rounded-md border border-line px-3 py-2 text-sm"
                value={form.seizoen_toelichting || ""} onChange={(e) => set("seizoen_toelichting", e.target.value)}
                placeholder="Bijv. zomer +30% door terrasmedewerkers"
              />
            </div>
          )}
          {error && <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</div>}
          <div className="flex items-center gap-3 border-t border-line pt-3">
            <IconButton icon={Check} variant="primary" onClick={save} disabled={saving}>{saving ? "Opslaan…" : "Opslaan"}</IconButton>
            <button className="text-sm text-slate-500 underline" onClick={() => setBewerken(false)}>Annuleren</button>
            {saved && <span className="text-sm font-medium text-emerald-700"><Check size={14} className="inline mr-0.5" />Opgeslagen</span>}
          </div>
        </div>
      )}
    </Panel>
  );
}

function ContactgegevensKaart({enrichment, vastgoed: initVastgoed, api, batchId, companyId, onRefresh}) {
  const e = enrichment || {};
  const [bewerken, setBewerken] = useState(false);
  const [form, setForm] = useState({
    website_url: e.website_url || "",
    telefoonnummer: e.telefoonnummer || "",
    email: e.email || "",
    correspondentieadres: initVastgoed?.correspondentieadres || "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function set(key, val) { setForm((p) => ({...p, [key]: val})); }

  async function save() {
    setSaving(true); setError("");
    try {
      await api.updateCompany(batchId, companyId, {
        website_url: form.website_url || null,
        telefoonnummer: form.telefoonnummer || null,
        email: form.email || null,
      });
      const vg = initVastgoed || {};
      await api.saveVastgoed(batchId, companyId, {
        perceel_opp: vg.perceel_opp ?? null,
        winkel_opp: vg.winkel_opp ?? null,
        kantoor_opp: vg.kantoor_opp ?? null,
        bedrijfs_opp: vg.bedrijfs_opp ?? null,
        uitbreidingsruimte: vg.uitbreidingsruimte ?? null,
        seizoensverschillen: vg.seizoensverschillen ?? null,
        seizoen_toelichting: vg.seizoen_toelichting ?? null,
        correspondentieadres: form.correspondentieadres || null,
      });
      setBewerken(false);
      if (onRefresh) await onRefresh();
    } catch (err) { setError(err.message); }
    finally { setSaving(false); }
  }

  const gevuld = [e.website_url, e.telefoonnummer, e.email, initVastgoed?.correspondentieadres].filter(Boolean).length;

  return (
    <Panel
      title="Contactgegevens"
      collapsible
      onEdit={() => setBewerken((b) => !b)}
      completeness={{gevuld, totaal: 4}}
    >
      {!bewerken ? (
        <dl className="grid gap-4 text-sm sm:grid-cols-2">
          <KennisVeld label="Website" value={e.website_url} type="link" />
          <KennisVeld label="Telefoon" value={e.telefoonnummer} />
          <KennisVeld label="E-mail" value={e.email} type="email" />
          <KennisVeld label="Correspondentieadres" value={initVastgoed?.correspondentieadres} tooltip="Postadres indien afwijkend van vestigingsadres" />
        </dl>
      ) : (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            {[
              {key: "website_url",         label: "Website",             placeholder: "https://…"},
              {key: "telefoonnummer",       label: "Telefoon",            placeholder: "+31 …"},
              {key: "email",               label: "E-mail",              placeholder: "info@…"},
              {key: "correspondentieadres", label: "Correspondentieadres", placeholder: "Postadres indien afwijkend"},
            ].map(({key, label, placeholder}) => (
              <div key={key}>
                <label className="mb-1 block text-xs font-medium text-slate-500">{label}</label>
                <input
                  className="focus-ring h-9 w-full rounded-md border border-line px-3 text-sm"
                  value={form[key]}
                  onChange={(ev) => set(key, ev.target.value)}
                  placeholder={placeholder}
                />
              </div>
            ))}
          </div>
          {error && <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</div>}
          <div className="flex items-center gap-3 border-t border-line pt-3">
            <IconButton icon={Check} variant="primary" onClick={save} disabled={saving}>{saving ? "Opslaan…" : "Opslaan"}</IconButton>
            <button className="text-sm text-slate-500 underline" onClick={() => setBewerken(false)}>Annuleren</button>
          </div>
        </div>
      )}
    </Panel>
  );
}

function WpHistorie({wp_historie}) {
  return (
    <Panel title="WP-historie" collapsible>
      {!wp_historie?.length ? (
        <p className="text-sm text-slate-400">Nog geen goedgekeurde records.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-line text-xs font-semibold uppercase tracking-wide text-slate-400">
                <th className="pb-2 pr-5">Jaar</th>
                <th className="pb-2 pr-5">WP</th>
                <th className="pb-2 pr-5">Bron</th>
                <th className="pb-2 pr-5">Status</th>
                <th className="pb-2">Goedgekeurd</th>
              </tr>
            </thead>
            <tbody>
              {wp_historie.map((r, i) => (
                <tr key={i} className="border-b border-line last:border-0">
                  <td className="py-2.5 pr-5 font-semibold">{r.wp_jaar}</td>
                  <td className="py-2.5 pr-5 font-bold text-etil">{r.wp_waarde}</td>
                  <td className="py-2.5 pr-5 text-slate-500">{r.bron_type || "—"}</td>
                  <td className="py-2.5 pr-5"><StatusPill status={r.status} /></td>
                  <td className="py-2.5 text-xs text-slate-400">
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

function VorigJaarVergelijking({vorig_jaar, huidig_wp, collapsible}) {
  if (!vorig_jaar) return null;
  const {wp_jaar, wp_waarde, verschil_abs, verschil_pct, signaal} = vorig_jaar;
  const isHoog = signaal === "hoog";
  const isPositief = verschil_abs != null && verschil_abs > 0;
  const isNegatief = verschil_abs != null && verschil_abs < 0;
  const pctTekst = verschil_pct != null
    ? `${isPositief ? "+" : ""}${(verschil_pct * (isNegatief ? -100 : 100)).toFixed(1)}%`
    : null;

  return (
    <Panel title="Vergelijking vorig jaar" collapsible={collapsible}>
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
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [gegevens, setGegevens] = useState({});
  const [widgetDone, setWidgetDone] = useState({wpBevestiging: false, wpDetails: false, correspondentie: false, oppervlakte: false});
  const [wpBevestigd, setWpBevestigd] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({behavior: "smooth"}); }, [messages, busy]);

  async function callMessage(msgs) {
    setBusy(true);
    try {
      const r = await fetch(`${API_URL}/chat/${token}/message`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({messages: msgs}),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Fout bij versturen");
      const updated = [...msgs, {role: "assistant", content: data.reply}];
      setMessages(updated);
      if (data.gegevens) setGegevens((prev) => ({...prev, ...data.gegevens}));
      if (data.done) setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    fetch(`${API_URL}/chat/${token}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.status === "completed") { setDone(true); return; }
        setSession(data);
        const initMsgs = data.messages || [];
        setMessages(initMsgs);
        if (initMsgs.length === 0) callMessage([]);
      })
      .catch(() => setError("Chat-sessie niet gevonden of verlopen."));
  }, [token]);

  async function sendText(text) {
    if (!text.trim() || busy) return;
    const newMsgs = [...messages, {role: "user", content: text.trim()}];
    setMessages(newMsgs);
    setInput("");
    await callMessage(newMsgs);
  }

  async function sendWidget(text, widgetKey) {
    setWidgetDone((prev) => ({...prev, [widgetKey]: true}));
    const newMsgs = [...messages, {role: "user", content: text}];
    setMessages(newMsgs);
    await callMessage(newMsgs);
  }

  // Widgets: primair op gegevens-voortgang, keyword als fallback
  // Nooit tonen voordat de gebruiker iets heeft getypt (userMsgCount >= 1)
  function currentWidget() {
    if (!session || done || busy) return null;
    const userMsgCount = messages.filter((m) => m.role === "user").length;
    if (userMsgCount < 1) return null;
    const lastAI = [...messages].reverse().find((m) => m.role === "assistant")?.content?.toLowerCase() || "";
    const aiMentions = (kws) => kws.some((k) => lastAI.includes(k));

    // Stap 1: WP bevestigen of invoeren (eigen standalone blok)
    if (!widgetDone.wpBevestiging && wpBevestigd == null && gegevens.wp_totaal == null && gegevens.eigen_personeel == null) {
      if (session?.pre_fill_wp != null || aiMentions(["uitsplitsing", "dienstverband", "invulformulier", "werkzame personen"]))
        return "wpBevestiging";
    }
    // Stap 2: Dienstverband + geslacht/arbeidsduur gecombineerd (2 stappen)
    if (!widgetDone.wpDetails && gegevens.man == null) {
      if (wpBevestigd != null || gegevens.wp_totaal != null || widgetDone.wpBevestiging)
        return "wpDetails";
    }
    // Correspondentie: AI vraagt ernaar
    if (!widgetDone.correspondentie && gegevens.correspondentieadres == null
        && aiMentions(["correspondentieadres", "hetzelfde als het vestigingsadres"]))
      return "correspondentie";
    // Oppervlakte: AI vraagt ernaar
    if (!widgetDone.oppervlakte && gegevens.perceeloppervlakte == null
        && aiMentions(["oppervlakte", "perceeloppervlakte", "m²", "vloeroppervlakte"]))
      return "oppervlakte";
    return null;
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

  if (!session && !error) return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5]">
      <div className="text-slate-500">Laden…</div>
    </main>
  );

  const widget = currentWidget();

  return (
    <main className="flex h-screen flex-col overflow-hidden bg-[#eef2f5]">
      {/* Header */}
      <div className="bg-white border-b border-line px-4 py-3 shadow-sm">
        <div className="mx-auto flex max-w-5xl items-center gap-4">
          <img src="/logo-limburg.png" alt="Provincie Limburg" className="h-10 w-auto" />
          <div>
            <div className="text-sm font-semibold text-ink">Vestigingsregister — {session?.bedrijfsnaam || ""}</div>
            <div className="text-xs text-slate-500">Provincie Limburg · Etil Research Group</div>
          </div>
        </div>
      </div>

      {/* Body: chat + overview panel */}
      <div className="mx-auto flex w-full max-w-5xl flex-1 gap-4 overflow-hidden p-4">
        {/* Chat column */}
        <div className="flex min-h-0 flex-1 flex-col gap-3">
          {/* Messages — scrollt intern */}
          <div className="flex flex-1 flex-col gap-3 overflow-y-auto">
            {messages.map((msg, i) => (
              <div key={i} className={classNames("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
                <div className={classNames(
                  "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap",
                  msg.role === "user"
                    ? "rounded-br-sm bg-etil text-white"
                    : "rounded-bl-sm border border-line bg-white text-slate-800 shadow-sm"
                )}>
                  {msg.content}
                </div>
              </div>
            ))}
            {busy && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-sm border border-line bg-white px-4 py-2.5 shadow-sm">
                  <span className="flex gap-1">
                    <span className="animate-bounce text-slate-400" style={{animationDelay: "0ms"}}>●</span>
                    <span className="animate-bounce text-slate-400" style={{animationDelay: "150ms"}}>●</span>
                    <span className="animate-bounce text-slate-400" style={{animationDelay: "300ms"}}>●</span>
                  </span>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Contextual form widget */}
          {!busy && widget === "wpBevestiging" && (
            <WpBevestigingBlok
              preFillWp={session?.pre_fill_wp || 0}
              onSubmit={(wpTotal, tekst) => {
                setWpBevestigd(wpTotal);
                sendWidget(tekst, "wpBevestiging");
              }}
              disabled={busy}
            />
          )}
          {!busy && widget === "wpDetails" && (
            <WpDetailsFormulier
              wpTotaal={wpBevestigd || gegevens.wp_totaal || 0}
              onSubmit={(txt) => sendWidget(txt, "wpDetails")}
              disabled={busy}
            />
          )}
          {!busy && widget === "correspondentie" && (
            <CorrespondentieadresFormulier
              vestigingsadres={session?.adres || ""}
              onSubmit={(txt) => sendWidget(txt, "correspondentie")}
              disabled={busy}
            />
          )}
          {!busy && widget === "oppervlakte" && (
            <OppervlakteFormulier
              onSubmit={(txt) => sendWidget(txt, "oppervlakte")}
              disabled={busy}
            />
          )}

          {/* Text input — verborgen als een widget actief is */}
          {error && <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</div>}
          {!widget && (
            <div className="flex gap-2">
              <input
                className="focus-ring flex-1 rounded-xl border border-line bg-white px-4 py-2.5 text-sm shadow-sm"
                placeholder={busy ? "Bezig…" : "Typ uw antwoord…"}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendText(input); }}}
                disabled={busy || done}
              />
              <button
                onClick={() => sendText(input)}
                disabled={!input.trim() || busy || done}
                className="focus-ring rounded-xl bg-etil px-4 py-2.5 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-40"
              >
                Stuur
              </button>
            </div>
          )}
          <p className="text-center text-xs text-slate-400">
            Uw gegevens worden uitsluitend gebruikt voor het Vestigingsregister van Provincie Limburg.
          </p>
        </div>

        {/* Overview panel (desktop only) — plakt aan de rechterkant */}
        <div className="hidden w-64 overflow-y-auto lg:block">
          <OverzichtPanel gegevens={gegevens} />
        </div>
      </div>
    </main>
  );
}

const OVERZICHT_GROEPEN = [
  {
    titel: "Personeel",
    velden: [
      {key: "wp_totaal", label: "WP totaal"},
      {key: "eigen_personeel", label: "Eigen personeel"},
      {key: "uitzend", label: "Uitzendkrachten"},
      {key: "detachering", label: "Detachering"},
      {key: "wsw", label: "WSW"},
      {key: "man", label: "Man"},
      {key: "vrouw", label: "Vrouw"},
      {key: "voltijd", label: "Voltijd"},
      {key: "deeltijd", label: "Deeltijd"},
      {key: "pct_op_locatie", label: "% op locatie"},
    ],
  },
  {
    titel: "Vastgoed",
    velden: [
      {key: "adres", label: "Vestigingsadres"},
      {key: "correspondentieadres", label: "Correspondentieadres"},
      {key: "perceeloppervlakte", label: "Perceeloppervlakte"},
      {key: "winkeloppervlakte", label: "Winkeloppervlakte"},
      {key: "kantooroppervlakte", label: "Kantooroppervlakte"},
      {key: "bedrijfsvloeroppervlakte", label: "Bedrijfsvloeroppervlakte"},
      {key: "uitbreidingsruimte", label: "Uitbreidingsruimte"},
    ],
  },
  {
    titel: "Overig",
    velden: [
      {key: "seizoensverschil", label: "Seizoensverschil"},
      {key: "opmerking", label: "Opmerking"},
    ],
  },
];

function OverzichtPanel({gegevens}) {
  const prevGegevensRef = useRef({});
  const merged = gegevens || {};
  const alleVelden = OVERZICHT_GROEPEN.flatMap((g) => g.velden);
  const ingevuld = alleVelden.filter((v) => merged[v.key] != null).length;
  const totaal = alleVelden.length;
  const pctVoortgang = totaal ? Math.round((ingevuld / totaal) * 100) : 0;
  const changedKeys = new Set();
  const prev = prevGegevensRef.current;
  for (const key of Object.keys(merged)) {
    if (merged[key] != null && prev[key] !== merged[key]) changedKeys.add(key);
  }
  useEffect(() => { prevGegevensRef.current = {...merged}; }, [gegevens]);
  return (
    <div className="flex flex-col rounded-lg border border-line bg-white shadow-sm max-h-[40vh] md:max-h-[85vh]">
      <div className="sticky top-0 z-10 rounded-t-lg border-b border-line bg-white p-4">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-semibold text-slate-700">Voortgang</span>
          <span className="font-bold text-etil">{pctVoortgang}%</span>
        </div>
        <div className="h-2 rounded-full bg-slate-200">
          <div className="h-2 rounded-full bg-etil transition-all duration-500" style={{width: `${pctVoortgang}%`}} />
        </div>
        <div className="mt-1 text-xs text-slate-400">{ingevuld} van {totaal} velden</div>
      </div>
      <div className="flex flex-col gap-4 overflow-y-auto p-4">
        {OVERZICHT_GROEPEN.map((groep) => {
          const groepIngevuld = groep.velden.filter((v) => merged[v.key] != null).length;
          const groepTotaal = groep.velden.length;
          const groepKlaar = groepIngevuld === groepTotaal;
          return (
            <div key={groep.titel}>
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-slate-500">
                {groepKlaar
                  ? <span className="flex h-4 w-4 items-center justify-center rounded-full bg-etil text-[10px] text-white">✓</span>
                  : <span className="flex h-4 w-4 items-center justify-center rounded-full border border-slate-300 text-[10px] text-slate-400">○</span>
                }
                {groep.titel}
                <span className="ml-auto font-normal text-slate-400">{groepIngevuld}/{groepTotaal}</span>
              </div>
              <div className="space-y-0.5">
                {groep.velden.map((veld) => {
                  const waarde = merged[veld.key];
                  const heeftWaarde = waarde != null;
                  const isChanged = changedKeys.has(veld.key);
                  return (
                    <div key={veld.key} className={classNames("flex items-center gap-2 rounded px-2 py-1 text-sm", isChanged && "field-pulse")}>
                      {heeftWaarde ? <span className="text-etil text-xs">✓</span> : <span className="text-xs text-slate-300">○</span>}
                      <span className={classNames("flex-1", heeftWaarde ? "text-slate-700" : "text-slate-400")}>{veld.label}</span>
                      <span className={classNames("text-right", heeftWaarde ? "font-semibold text-slate-900" : "text-slate-300")}>
                        {heeftWaarde ? String(waarde) : "—"}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function SomRij({velden, wpTotaal, values, onUpdate, disabled}) {
  const som = velden.reduce((s, v) => s + (Number(values[v.key]) || 0), 0);
  const resterend = wpTotaal - som;
  return (
    <div className="mb-3">
      <div className="mb-1 grid gap-2" style={{gridTemplateColumns: `repeat(${velden.length}, 1fr)`}}>
        {velden.map((v) => (
          <div key={v.key}>
            <label className="mb-1 block text-xs text-slate-600">{v.label}</label>
            <input type="number" min="0" max={wpTotaal}
              className="focus-ring h-9 w-full rounded-md border border-line px-2 text-sm text-center"
              value={values[v.key] ?? ""} onChange={(e) => onUpdate(v.key, e.target.value)} disabled={disabled} />
          </div>
        ))}
      </div>
      <span className={classNames("text-xs font-medium", resterend === 0 ? "text-emerald-600" : resterend < 0 ? "text-red-600" : "text-amber-600")}>
        {resterend === 0 ? "✓ Som klopt" : resterend > 0 ? `Nog ${resterend} te verdelen` : `${Math.abs(resterend)} te veel`}
      </span>
    </div>
  );
}

function WpBevestigingBlok({preFillWp, onSubmit, disabled}) {
  const heeftSchatting = preFillWp > 0;
  const [keuze, setKeuze] = useState(heeftSchatting ? null : "invoeren");
  const [invoer, setInvoer] = useState("");
  function bevestig(totaal, label) { onSubmit(totaal, label); }
  return (
    <div className="rounded-lg border border-etil/30 bg-etil/5 p-3">
      <div className="mb-2 text-xs font-semibold uppercase text-etil">
        {heeftSchatting ? "WP-getal bevestigen" : "WP-totaal invoeren"}
      </div>
      {heeftSchatting && keuze === null && (
        <>
          <div className="mb-2 text-sm text-slate-700">
            Geschat aantal werkzame personen: <strong>{preFillWp}</strong>
          </div>
          <div className="flex gap-2">
            <button type="button" disabled={disabled}
              onClick={() => bevestig(preFillWp, `WP totaal: ${preFillWp} (bevestigd)`)}
              className="focus-ring flex-1 rounded-md bg-etil px-3 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-40">
              Ja, klopt
            </button>
            <button type="button" disabled={disabled} onClick={() => setKeuze("corrigeren")}
              className="focus-ring flex-1 rounded-md border border-line bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-panel disabled:opacity-40">
              Nee, klopt niet
            </button>
          </div>
        </>
      )}
      {(keuze === "corrigeren" || keuze === "invoeren") && (
        <>
          {keuze === "corrigeren" && (
            <div className="mb-2 text-sm text-slate-500">
              Geschat: <strong>{preFillWp}</strong> — voer het juiste aantal in
            </div>
          )}
          <div className="flex gap-2">
            <input type="number" min="1"
              className="focus-ring h-10 flex-1 rounded-md border border-line px-3 text-sm"
              value={invoer} onChange={(e) => setInvoer(e.target.value)}
              placeholder={heeftSchatting ? "Juiste aantal WP" : "Totaal aantal WP"}
              autoFocus disabled={disabled} />
            <button type="button" disabled={!invoer || disabled}
              onClick={() => {
                const totaal = Number(invoer);
                const label = keuze === "corrigeren"
                  ? `WP totaal: ${totaal} (gecorrigeerd van ${preFillWp})`
                  : `WP totaal: ${totaal}`;
                bevestig(totaal, label);
              }}
              className="focus-ring rounded-md bg-etil px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-40">
              Verzenden
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function WpDetailsFormulier({wpTotaal, onSubmit, disabled}) {
  const [stap, setStap] = useState(0);
  const [values, setValues] = useState({});
  const dienstVelden = [
    {key: "eigen_personeel", label: "Eigen personeel"},
    {key: "uitzend", label: "Uitzendkrachten"},
    {key: "detachering", label: "Detachering"},
    {key: "wsw", label: "WSW"},
  ];
  const geslacht = [{key: "man", label: "Man"}, {key: "vrouw", label: "Vrouw"}];
  const arbeid = [{key: "voltijd", label: "Voltijd"}, {key: "deeltijd", label: "Deeltijd"}];
  const somDienst = dienstVelden.reduce((s, v) => s + (Number(values[v.key]) || 0), 0);
  const somGeslacht = geslacht.reduce((s, v) => s + (Number(values[v.key]) || 0), 0);
  const somArbeid = arbeid.reduce((s, v) => s + (Number(values[v.key]) || 0), 0);
  const pctIngevuld = values.pct_op_locatie !== undefined && values.pct_op_locatie !== "";
  function update(key, val) { setValues((p) => ({...p, [key]: val})); }
  function verstuur() {
    if (somGeslacht !== wpTotaal || somArbeid !== wpTotaal || !pctIngevuld) return;
    const parts = [
      ...dienstVelden.map((v) => `${v.label}: ${values[v.key] || 0}`),
      ...geslacht.map((v) => `${v.label}: ${values[v.key] || 0}`),
      ...arbeid.map((v) => `${v.label}: ${values[v.key] || 0}`),
      `% werkzaam op locatie: ${values.pct_op_locatie}%`,
    ];
    onSubmit(parts.join(", "));
  }
  return (
    <div className="rounded-lg border border-etil/30 bg-etil/5 p-3">
      {stap === 0 && (
        <>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-etil">Dienstverband</span>
            <span className="text-xs text-slate-500">Totaal WP: <strong>{wpTotaal}</strong></span>
          </div>
          <SomRij velden={dienstVelden} wpTotaal={wpTotaal} values={values} onUpdate={update} disabled={disabled} />
          <div className="flex justify-end">
            <button type="button" disabled={somDienst !== wpTotaal || disabled} onClick={() => setStap(1)}
              className="focus-ring rounded-md bg-etil px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-40">
              Volgende
            </button>
          </div>
        </>
      )}
      {stap === 1 && (
        <>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-etil">Geslacht & Arbeidsduur</span>
            <span className="text-xs text-slate-500">Totaal WP: <strong>{wpTotaal}</strong></span>
          </div>
          <SomRij velden={geslacht} wpTotaal={wpTotaal} values={values} onUpdate={update} disabled={disabled} />
          <SomRij velden={arbeid} wpTotaal={wpTotaal} values={values} onUpdate={update} disabled={disabled} />
          <div className="mb-3">
            <label className="mb-1 block text-xs text-slate-600">% werkzaam op locatie (≥60% van de tijd)</label>
            <input type="number" min="0" max="100" className="focus-ring h-9 w-32 rounded-md border border-line px-2 text-sm text-center"
              value={values.pct_op_locatie ?? ""} onChange={(e) => update("pct_op_locatie", e.target.value)} placeholder="%" disabled={disabled} />
          </div>
          <div className="flex justify-end">
            <button type="button" disabled={somGeslacht !== wpTotaal || somArbeid !== wpTotaal || !pctIngevuld || disabled} onClick={verstuur}
              className="focus-ring rounded-md bg-etil px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-40">
              Verstuur
            </button>
          </div>
        </>
      )}
      <div className="mt-2 flex gap-1">
        <div className="h-1 flex-1 rounded-full bg-etil" />
        <div className={classNames("h-1 flex-1 rounded-full", stap >= 1 ? "bg-etil" : "bg-slate-200")} />
      </div>
    </div>
  );
}

function CorrespondentieadresFormulier({vestigingsadres, onSubmit, disabled}) {
  const [keuze, setKeuze] = useState(null);
  const [adres, setAdres] = useState("");
  return (
    <div className="rounded-lg border border-etil/30 bg-etil/5 p-3">
      <div className="mb-2 text-xs font-semibold uppercase text-etil">Correspondentieadres</div>
      <div className="mb-2 text-sm text-slate-700">Is het correspondentieadres hetzelfde als het vestigingsadres{vestigingsadres ? ` (${vestigingsadres})` : ""}?</div>
      {keuze === null && (
        <div className="flex gap-2">
          <button type="button" disabled={disabled} onClick={() => { setKeuze("ja"); onSubmit("Correspondentieadres: zelfde als vestigingsadres"); }}
            className="focus-ring flex-1 rounded-md bg-etil px-3 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-40">Ja, zelfde adres</button>
          <button type="button" disabled={disabled} onClick={() => setKeuze("nee")}
            className="focus-ring flex-1 rounded-md border border-line bg-white px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-panel disabled:opacity-40">Nee, ander adres</button>
        </div>
      )}
      {keuze === "nee" && (
        <div className="flex gap-2">
          <input type="text" className="focus-ring h-10 flex-1 rounded-md border border-line px-3 text-sm"
            value={adres} onChange={(e) => setAdres(e.target.value)} placeholder="Correspondentieadres" autoFocus disabled={disabled} />
          <button type="button" disabled={!adres.trim() || disabled} onClick={() => onSubmit(`Correspondentieadres: ${adres.trim()}`)}
            className="focus-ring rounded-md bg-etil px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-40">Verstuur</button>
        </div>
      )}
    </div>
  );
}

function OppervlakteFormulier({onSubmit, disabled}) {
  const [values, setValues] = useState({});
  const [uitbreiding, setUitbreiding] = useState(null);
  const [uitbreidingTekst, setUitbreidingTekst] = useState("");
  const velden = [
    {key: "perceeloppervlakte", label: "Perceel"},
    {key: "winkeloppervlakte", label: "Winkel"},
    {key: "kantooroppervlakte", label: "Kantoor"},
    {key: "bedrijfsvloeroppervlakte", label: "Bedrijfsvloer"},
  ];
  function update(key, val) { setValues((p) => ({...p, [key]: val})); }
  const alleIngevuld = velden.every((v) => values[v.key] !== undefined && values[v.key] !== "");
  const uitbreidingKlaar = uitbreiding === "nee" || (uitbreiding === "ja" && uitbreidingTekst.trim());
  const kanVersturen = alleIngevuld && uitbreidingKlaar;
  function verstuur() {
    if (!kanVersturen) return;
    const parts = velden.map((v) => `${v.label}oppervlakte: ${values[v.key]} m²`);
    parts.push(uitbreiding === "ja" ? `Uitbreidingsruimte: ${uitbreidingTekst.trim()}` : "Uitbreidingsruimte: geen");
    onSubmit(parts.join(", "));
  }
  return (
    <div className="rounded-lg border border-etil/30 bg-etil/5 p-3">
      <div className="mb-2 text-xs font-semibold uppercase text-etil">Oppervlaktes</div>
      <div className="mb-3 grid grid-cols-2 gap-2">
        {velden.map((v) => (
          <div key={v.key}>
            <label className="mb-1 block text-xs text-slate-600">{v.label}</label>
            <div className="relative">
              <input type="number" min="0" className="focus-ring h-9 w-full rounded-md border border-line px-2 pr-8 text-sm text-center"
                value={values[v.key] ?? ""} onChange={(e) => update(v.key, e.target.value)} disabled={disabled} />
              <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-xs text-slate-400">m²</span>
            </div>
          </div>
        ))}
      </div>
      <div className="mb-2">
        <div className="mb-1 text-xs text-slate-600">Is er uitbreidingsruimte?</div>
        {uitbreiding === null && (
          <div className="flex gap-2">
            <button type="button" disabled={disabled} onClick={() => setUitbreiding("ja")}
              className="focus-ring flex-1 rounded-md border border-line bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-panel disabled:opacity-40">Ja</button>
            <button type="button" disabled={disabled} onClick={() => setUitbreiding("nee")}
              className="focus-ring flex-1 rounded-md border border-line bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-panel disabled:opacity-40">Nee</button>
          </div>
        )}
        {uitbreiding === "ja" && (
          <input type="text" className="focus-ring h-9 w-full rounded-md border border-line px-2 text-sm"
            value={uitbreidingTekst} onChange={(e) => setUitbreidingTekst(e.target.value)}
            placeholder="Beschrijf de uitbreidingsruimte" autoFocus disabled={disabled} />
        )}
        {uitbreiding === "nee" && <span className="text-xs text-slate-500">Geen uitbreidingsruimte</span>}
      </div>
      <div className="flex justify-end">
        <button type="button" disabled={!kanVersturen || disabled} onClick={verstuur}
          className="focus-ring rounded-md bg-etil px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-40">Verstuur</button>
      </div>
    </div>
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

// Alle velden van de AI-chatflow met label en groepering
const CHAT_VELDEN = [
  {groep: "Personeel — totaal & type", velden: [
    {key: "wp_totaal", label: "Totaal werkzame personen (wp_totaal)"},
    {key: "eigen_personeel", label: "Eigen personeel in loondienst"},
    {key: "uitzend", label: "Uitzendkrachten"},
    {key: "detachering", label: "Gedetacheerden"},
    {key: "wsw", label: "WSW-personeel"},
  ]},
  {groep: "Personeel — geslacht & arbeidsduur", velden: [
    {key: "man", label: "Mannen"},
    {key: "vrouw", label: "Vrouwen"},
    {key: "voltijd", label: "Voltijd"},
    {key: "deeltijd", label: "Deeltijd"},
    {key: "pct_op_locatie", label: "% werkzaam op dit vestigingsadres"},
  ]},
  {groep: "Locatie & adres", velden: [
    {key: "adres", label: "Vestigingsadres"},
    {key: "correspondentieadres", label: "Correspondentieadres"},
  ]},
  {groep: "Vastgoed & ruimte", velden: [
    {key: "perceeloppervlakte", label: "Perceeloppervlakte (m²)"},
    {key: "winkeloppervlakte", label: "Winkeloppervlakte (m²)"},
    {key: "kantooroppervlakte", label: "Kantooroppervlakte (m²)"},
    {key: "bedrijfsvloeroppervlakte", label: "Bedrijfsvloeroppervlakte (m²)"},
    {key: "uitbreidingsruimte", label: "Uitbreidingsruimte beschikbaar"},
  ]},
  {groep: "Overig", velden: [
    {key: "seizoensverschil", label: "Seizoensverschillen in personeel"},
    {key: "opmerking", label: "Overige opmerkingen / toelichting"},
  ]},
];

const STANDAARD_VELD_CONFIG = {
  wp_totaal: true, eigen_personeel: true, uitzend: true,
  detachering: true, wsw: true, man: true, vrouw: true,
  voltijd: true, deeltijd: true, pct_op_locatie: true,
  adres: true, correspondentieadres: true,
  perceeloppervlakte: true, winkeloppervlakte: true,
  kantooroppervlakte: true, bedrijfsvloeroppervlakte: true,
  uitbreidingsruimte: true, seizoensverschil: true, opmerking: true,
};

function leegTemplate() {
  return {
    naam: "Nieuw template",
    beschrijving: "",
    veld_config: {...STANDAARD_VELD_CONFIG},
    intro_tekst: "",
    extra_vragen: [],
    is_default: false,
  };
}

function templateNaarEditor(t) {
  const cfg = {...STANDAARD_VELD_CONFIG};
  for (const [k, v] of Object.entries(t.veld_config || {})) {
    if (k in cfg) {
      if (typeof v === "boolean") cfg[k] = v;
      else if (v === "skip") cfg[k] = false;
      else cfg[k] = true; // "verplicht" of "optioneel" (oud formaat)
    }
  }
  return {
    ...t,
    veld_config: cfg,
    intro_tekst: t.intro_tekst || "",
    extra_vragen: (t.extra_vragen || []).filter((v) => v.trim()),
  };
}

function editorNaarBody(sel) {
  return {
    naam: sel.naam,
    beschrijving: sel.beschrijving,
    veld_config: sel.veld_config,
    intro_tekst: sel.intro_tekst || "",
    extra_vragen: (sel.extra_vragen || []).filter((v) => v.trim()),
    is_default: sel.is_default,
  };
}

function ChatTemplatesView({api, user, onLogout, openDashboard}) {
  const [templates, setTemplates] = useState([]);
  const [selected, setSelected] = useState(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function load() {
    const data = await api.chatTemplates();
    setTemplates(data);
  }

  useEffect(() => { load().catch((err) => setError(err.message)); }, []);

  function newTemplate() {
    setSelected(leegTemplate());
    setSaved(false);
    setError("");
  }

  function editTemplate(t) {
    setSelected(templateNaarEditor(t));
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
      const body = editorNaarBody(selected);
      if (selected.id) {
        await api.updateTemplate(selected.id, body);
      } else {
        const result = await api.createTemplate(body);
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

  function toggleVeld(key) {
    setSelected((prev) => ({
      ...prev,
      veld_config: {...(prev.veld_config || {}), [key]: !(prev.veld_config || {})[key]},
    }));
    setSaved(false);
  }

  function setExtraVraag(i, value) {
    setSelected((prev) => {
      const eq = [...(prev.extra_vragen || [])];
      eq[i] = value;
      return {...prev, extra_vragen: eq};
    });
    setSaved(false);
  }

  function addExtraVraag() {
    setSelected((prev) => ({...prev, extra_vragen: [...(prev.extra_vragen || []), ""]}));
    setSaved(false);
  }

  function removeExtraVraag(i) {
    setSelected((prev) => {
      const eq = [...(prev.extra_vragen || [])];
      eq.splice(i, 1);
      return {...prev, extra_vragen: eq};
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
      <div className="grid gap-5 lg:grid-cols-[300px_1fr]">
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
                  <div className="mt-1.5 flex gap-2 text-xs">
                    <span className="rounded border border-etil/20 bg-etil/5 px-1.5 py-0.5 text-etil">
                      {t.n_actief ?? Object.values(t.veld_config || {}).filter(Boolean).length} velden aan
                    </span>
                    {(t.extra_vragen || []).length > 0 && (
                      <span className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 text-slate-500">
                        +{t.extra_vragen.length} extra
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  {t.is_default ? <span className="rounded bg-etil/10 px-1.5 py-0.5 text-xs font-semibold text-etil">Standaard</span> : null}
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
          <div className="space-y-5">
            {/* Basisinfo */}
            <div className="rounded-lg border border-line bg-white p-5">
              <h3 className="mb-4 text-sm font-semibold">Algemeen</h3>
              <div className="grid gap-4">
                <div>
                  <label className="mb-1 block text-sm font-medium">Naam</label>
                  <input
                    className="focus-ring h-10 w-full rounded-md border border-line px-3 text-sm"
                    value={selected.naam}
                    onChange={(e) => setField("naam", e.target.value)}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">Beschrijving <span className="font-normal text-slate-400">(optioneel)</span></label>
                  <input
                    className="focus-ring h-10 w-full rounded-md border border-line px-3 text-sm"
                    value={selected.beschrijving || ""}
                    onChange={(e) => setField("beschrijving", e.target.value)}
                    placeholder="Bijv. 'Volledig — alle velden'"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">
                    Aangepaste openingstekst <span className="font-normal text-slate-400">(optioneel — overschrijft standaard-opening)</span>
                  </label>
                  <textarea
                    className="focus-ring w-full rounded-md border border-line px-3 py-2 text-sm"
                    rows={3}
                    value={selected.intro_tekst || ""}
                    onChange={(e) => setField("intro_tekst", e.target.value)}
                    placeholder="Leeg = standaard Etil-opening gebruiken"
                  />
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selected.is_default}
                    onChange={(e) => setField("is_default", e.target.checked)}
                  />
                  <span>Standaard-template <span className="text-slate-400">(automatisch gebruikt bij nieuwe uitnodigingen)</span></span>
                </label>
              </div>
            </div>

            {/* Velden configuratie */}
            <div className="rounded-lg border border-line bg-white p-5">
              <h3 className="mb-3 text-sm font-semibold">Welke velden uitvragen?</h3>
              <div className="space-y-5">
                {CHAT_VELDEN.map(({groep, velden}) => (
                  <div key={groep}>
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">{groep}</div>
                    <div className="space-y-1">
                      {velden.map(({key, label}) => {
                        const aan = (selected.veld_config || {})[key] !== false;
                        return (
                          <div key={key} className="flex items-center justify-between gap-3 rounded-md px-2 py-1.5 hover:bg-panel">
                            <span className={classNames("text-sm", !aan && "text-slate-400 line-through")}>{label}</span>
                            <button
                              onClick={() => toggleVeld(key)}
                              className={classNames(
                                "relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors",
                                aan ? "bg-etil" : "bg-slate-200",
                              )}
                            >
                              <span className={classNames(
                                "block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform",
                                aan ? "translate-x-4" : "translate-x-1",
                              )} />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Extra vragen */}
            <div className="rounded-lg border border-line bg-white p-5">
              <h3 className="mb-1 text-sm font-semibold">Extra vragen</h3>
              <p className="mb-3 text-xs text-slate-500">Aanvullende vragen die de AI stelt. De antwoorden worden opgeslagen als extra_1, extra_2, …</p>
              <div className="space-y-2">
                {(selected.extra_vragen || []).map((v, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="w-5 shrink-0 text-center text-xs text-slate-400">{i + 1}.</span>
                    <input
                      className="focus-ring h-9 flex-1 rounded-md border border-line px-3 text-sm"
                      value={v}
                      onChange={(e) => setExtraVraag(i, e.target.value)}
                      placeholder="Stel een extra vraag…"
                    />
                    <button
                      onClick={() => removeExtraVraag(i)}
                      className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
                    >
                      <X size={14} />
                    </button>
                  </div>
                ))}
                <button
                  onClick={addExtraVraag}
                  className="flex items-center gap-1.5 text-sm text-etil hover:underline"
                >
                  <Plus size={14} /> Vraag toevoegen
                </button>
              </div>
            </div>

            {/* Opslaan */}
            <div className="flex items-center gap-3">
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

function JaarverslagenView({api, user, onLogout, openDashboard, openChat}) {
  const fileRef = useRef(null);
  const [uploads, setUploads] = useState([]);
  const [companies, setCompanies] = useState([]);
  const [companyZoek, setCompanyZoek] = useState("");
  const [selectedCompany, setSelectedCompany] = useState(null);
  const [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [error, setError] = useState("");
  const [zoek, setZoek] = useState("");
  const [jaar, setJaar] = useState(String(new Date().getFullYear()));
  const [uploadInfo, setUploadInfo] = useState(null);

  async function load() {
    const data = await api.jaarverslagen();
    setUploads(data);
  }

  useEffect(() => { load().catch((e) => setError(e.message)); }, []);

  useEffect(() => {
    const timer = setTimeout(async () => {
      try {
        const data = await api.zoekCompanies(companyZoek);
        setCompanies(data);
      } catch {}
    }, 300);
    return () => clearTimeout(timer);
  }, [companyZoek]);

  async function upload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    setUploadInfo(null);
    try {
      const result = await api.uploadJaarverslag(file, jaar || null, selectedCompany?.id || null);
      setUploadInfo({paginas: result.paginas, naam: result.bestandsnaam});
      await load();
      openChat(result.upload_id);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  async function verwijder(e, uploadId, naam) {
    e.stopPropagation();
    if (!window.confirm(`"${naam}" en alle chatberichten definitief verwijderen?`)) return;
    setDeleting(uploadId);
    try {
      await api.verwijderJaarverslag(uploadId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeleting(null);
    }
  }

  const gefilterd = useMemo(() =>
    uploads.filter((u) => {
      if (!zoek) return true;
      return (u.bestandsnaam + (u.company_naam || "")).toLowerCase().includes(zoek.toLowerCase());
    }), [uploads, zoek]);

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title="Jaarverslagen"
      actions={
        <>
          <IconButton icon={ListChecks} onClick={openDashboard}>Dashboard</IconButton>
          <input ref={fileRef} type="file" accept="application/pdf,.pdf" className="hidden" onChange={upload} />
          <IconButton icon={FileUp} variant="primary" onClick={() => fileRef.current?.click()} disabled={busy}>
            {busy ? "Uploaden…" : "PDF uploaden"}
          </IconButton>
        </>
      }
    >
      {error ? <Alert message={error} /> : null}

      {/* Upload-opties */}
      <div className="mb-4 flex flex-wrap gap-3 rounded-lg border border-line bg-white p-4">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500">Peiljaar</label>
          <input
            className="focus-ring h-10 w-24 rounded-md border border-line bg-white px-3 text-sm"
            value={jaar}
            onChange={(e) => setJaar(e.target.value)}
            placeholder="Jaar"
            inputMode="numeric"
          />
        </div>
        <div className="flex-1 min-w-48">
          <label className="mb-1 block text-xs font-medium text-slate-500">Koppel aan bedrijf (optioneel)</label>
          <div className="relative">
            <input
              className="focus-ring h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
              value={selectedCompany ? selectedCompany.naam : companyZoek}
              onChange={(e) => { setCompanyZoek(e.target.value); setSelectedCompany(null); }}
              placeholder="Zoek op bedrijfsnaam…"
            />
            {!selectedCompany && companies.length > 0 && companyZoek && (
              <div className="absolute z-10 mt-1 w-full rounded-md border border-line bg-white shadow-lg">
                {companies.map((c) => (
                  <button
                    key={c.id}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-panel"
                    onClick={() => { setSelectedCompany(c); setCompanyZoek(""); setCompanies([]); }}
                  >
                    <span className="font-medium">{c.naam}</span>
                    <span className="text-xs text-slate-400">{c.gemeente} · {c.batch_naam}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          {selectedCompany && (
            <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
              <span className="font-medium text-etil">{selectedCompany.naam}</span>
              <button className="text-slate-400 hover:text-red-500" onClick={() => setSelectedCompany(null)}>
                <X size={12} />
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Zoekbalk */}
      <div className="mb-4 relative">
        <Search className="pointer-events-none absolute left-3 top-3 text-slate-400" size={17} />
        <input
          className="focus-ring h-11 w-full rounded-md border border-line bg-white pl-9 pr-3"
          value={zoek}
          onChange={(e) => setZoek(e.target.value)}
          placeholder="Zoek op bestandsnaam of bedrijf…"
        />
      </div>

      <div className="overflow-hidden rounded-lg border border-line bg-white">
        <table className="w-full border-collapse text-left text-sm">
          <thead className="bg-panel text-xs uppercase text-slate-500">
            <tr>
              <th className="px-4 py-3">Bestand</th>
              <th className="px-4 py-3">Bedrijf</th>
              <th className="px-4 py-3">Jaar</th>
              <th className="px-4 py-3">Berichten</th>
              <th className="px-4 py-3">Geüpload</th>
              <th className="w-12 px-4 py-3"></th>
            </tr>
          </thead>
          <tbody>
            {gefilterd.map((u) => (
              <tr key={u.upload_id} className="cursor-pointer border-t border-line hover:bg-panel" onClick={() => openChat(u.upload_id)}>
                <td className="px-4 py-3 font-semibold text-etil">{u.bestandsnaam}</td>
                <td className="px-4 py-3 text-slate-500">{u.company_naam || "—"}</td>
                <td className="px-4 py-3">{u.jaar || "—"}</td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center gap-1 rounded-md border border-line bg-white px-2 py-1 text-xs">
                    <MessageSquare size={11} />{u.aantal_berichten}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-500">{new Date(u.uploaded_at).toLocaleDateString("nl-NL")}</td>
                <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
                  <button
                    className="rounded-md p-1.5 text-slate-400 transition hover:bg-red-50 hover:text-red-600"
                    onClick={(e) => verwijder(e, u.upload_id, u.bestandsnaam)}
                    disabled={deleting === u.upload_id}
                    title="Verwijderen"
                  >
                    <Trash2 size={15} />
                  </button>
                </td>
              </tr>
            ))}
            {!gefilterd.length ? (
              <tr><td className="px-4 py-8 text-center text-slate-500" colSpan="6">
                {uploads.length ? "Geen resultaten voor deze zoekopdracht" : "Geen jaarverslagen geüpload — kies een peiljaar en klik PDF uploaden"}
              </td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </Shell>
  );
}

function JaarverslagChatView({api, user, onLogout, uploadId, openJaarverslagen}) {
  const [detail, setDetail] = useState(null);
  const [vraag, setVraag] = useState("");
  const [wpWaarde, setWpWaarde] = useState("");
  const [wpJaar, setWpJaar] = useState(String(new Date().getFullYear() - 1));
  const [busy, setBusy] = useState(false);
  const [wpBusy, setWpBusy] = useState(false);
  const [wpOpgeslagen, setWpOpgeslagen] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef(null);

  async function load() {
    const data = await api.jaarverslag(uploadId);
    setDetail(data);
  }

  useEffect(() => { load().catch((e) => setError(e.message)); }, [uploadId]);
  useEffect(() => { bottomRef.current?.scrollIntoView({behavior: "smooth"}); }, [detail?.berichten?.length]);

  async function stuurVraag(e) {
    e.preventDefault();
    if (!vraag.trim() || busy) return;
    setBusy(true);
    setError("");
    const q = vraag;
    setVraag("");
    try {
      await api.chatJaarverslag(uploadId, q);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function opslaanWP() {
    if (!wpWaarde) return;
    setWpBusy(true);
    setError("");
    try {
      await api.opslaanWP(uploadId, Number(wpWaarde), Number(wpJaar));
      setWpOpgeslagen(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setWpBusy(false);
    }
  }

  const u = detail?.upload;
  const berichten = detail?.berichten || [];

  return (
    <Shell
      user={user}
      onLogout={onLogout}
      title={u?.bestandsnaam || "Jaarverslag chat"}
      actions={<IconButton icon={BookOpen} onClick={openJaarverslagen}>Jaarverslagen</IconButton>}
    >
      {error ? <Alert message={error} /> : null}
      <div className="grid gap-5 lg:grid-cols-[2fr_1fr]">
        <div className="flex flex-col gap-4">
          <Panel title="Chat met jaarverslag" subtitle={u ? `${u.jaar || "—"} · ${u.bestandsnaam}` : ""}>
            <div className="min-h-64 space-y-3">
              {!berichten.length ? (
                <div className="rounded-md border border-dashed border-line p-6 text-center text-sm text-slate-400">
                  Stel een vraag over dit jaarverslag, bijv. "Hoeveel medewerkers had dit bedrijf in {u?.jaar || "dit jaar"}?"
                </div>
              ) : berichten.map((b, i) => (
                <div key={i} className={classNames("flex flex-col gap-0.5", b.rol === "user" ? "items-end" : "items-start")}>
                  <div className={classNames(
                    "max-w-prose rounded-lg px-4 py-2.5 text-sm",
                    b.rol === "user"
                      ? "bg-etil text-white"
                      : "border border-line bg-panel text-ink",
                  )}>
                    {b.inhoud}
                  </div>
                  {b.created_at && (
                    <span className="text-xs text-slate-400">
                      {new Date(b.created_at).toLocaleTimeString("nl-NL", {hour: "2-digit", minute: "2-digit"})}
                    </span>
                  )}
                </div>
              ))}
              {busy ? (
                <div className="flex justify-start">
                  <div className="rounded-lg border border-line bg-panel px-4 py-2.5 text-sm text-slate-400">Bezig…</div>
                </div>
              ) : null}
              <div ref={bottomRef} />
            </div>
          </Panel>
          <form onSubmit={stuurVraag} className="flex gap-2">
            <input
              className="focus-ring h-11 flex-1 rounded-md border border-line bg-white px-3 text-sm"
              value={vraag}
              onChange={(e) => setVraag(e.target.value)}
              placeholder="Stel een vraag over het jaarverslag…"
              disabled={busy}
            />
            <IconButton icon={Send} variant="primary" type="submit" disabled={busy || !vraag.trim()}>
              {busy ? "…" : "Sturen"}
            </IconButton>
          </form>
        </div>

        <Panel title="WP-waarde opslaan" subtitle="Sla gevonden waarde op in het register">
          <div className="space-y-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-500">WP-waarde</label>
              <input
                className="focus-ring h-10 w-full rounded-md border border-line px-3 text-sm"
                type="number"
                min="0"
                value={wpWaarde}
                onChange={(e) => setWpWaarde(e.target.value)}
                placeholder="Bijv. 138"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-500">Peiljaar</label>
              <input
                className="focus-ring h-10 w-full rounded-md border border-line px-3 text-sm"
                type="number"
                value={wpJaar}
                onChange={(e) => setWpJaar(e.target.value)}
              />
            </div>
            {wpOpgeslagen ? (
              <div className="flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-800">
                <Check size={15} /> Opgeslagen in register
              </div>
            ) : (
              <IconButton
                icon={Check}
                variant="primary"
                className="w-full justify-center"
                onClick={opslaanWP}
                disabled={wpBusy || !wpWaarde}
              >
                {wpBusy ? "Opslaan…" : "Opslaan in register"}
              </IconButton>
            )}
            {u?.company_naam ? (
              <div className="mt-3 border-t border-line pt-3 text-xs text-slate-500">
                Bedrijf: <span className="font-medium text-ink">{u.company_naam}</span>
              </div>
            ) : (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                Niet gekoppeld aan een bedrijf — opslaan in register niet mogelijk
              </div>
            )}
          </div>
        </Panel>
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
