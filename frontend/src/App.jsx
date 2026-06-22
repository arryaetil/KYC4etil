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

const OVERZICHT_GROEPEN = [
  {
    titel: "Personeel",
    velden: [
      {key: "wp_totaal", label: "WP totaal", verplicht: true},
      {key: "eigen_personeel", label: "Eigen personeel", verplicht: true},
      {key: "uitzend", label: "Uitzendkrachten", verplicht: true},
      {key: "detachering", label: "Detachering", verplicht: true},
      {key: "wsw", label: "WSW", verplicht: true},
      {key: "man", label: "Man", verplicht: true},
      {key: "vrouw", label: "Vrouw", verplicht: true},
      {key: "voltijd", label: "Voltijd", verplicht: true},
      {key: "deeltijd", label: "Deeltijd", verplicht: true},
      {key: "pct_op_locatie", label: "% op locatie", verplicht: true},
    ],
  },
  {
    titel: "Vastgoed",
    velden: [
      {key: "adres", label: "Vestigingsadres", verplicht: true},
      {key: "correspondentieadres", label: "Correspondentieadres", verplicht: false},
      {key: "perceeloppervlakte", label: "Perceeloppervlakte", verplicht: true},
      {key: "winkeloppervlakte", label: "Winkeloppervlakte", verplicht: true},
      {key: "kantooroppervlakte", label: "Kantooroppervlakte", verplicht: true},
      {key: "bedrijfsvloeroppervlakte", label: "Bedrijfsvloeroppervlakte", verplicht: true},
      {key: "uitbreidingsruimte", label: "Uitbreidingsruimte", verplicht: false},
    ],
  },
  {
    titel: "Overig",
    velden: [
      {key: "seizoensverschil", label: "Seizoensverschil", verplicht: false},
      {key: "opmerking", label: "Opmerking", verplicht: false},
    ],
  },
];

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
                <td className="px-4 py-3"><StatusPill status={batch.status} /></td>
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
          {isRunning
            ? <IconButton icon={Square} variant="quiet" onClick={cancelBatch} disabled={busy}>Annuleren</IconButton>
            : <IconButton icon={Play} variant="primary" onClick={runBatch} disabled={busy}>Run</IconButton>
          }
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
        <select className="focus-ring h-11 rounded-md border border-line bg-white px-3" value={label} onChange={(event) => setLabel(event.target.value)}>
          <option value="">Alle labels</option>
          <option value="hoog">Groen</option>
          <option value="middel">Geel</option>
          <option value="laag">Rood</option>
          <option value="fouten">Fouten</option>
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
                    {company.pipeline_error && <AlertTriangle size={14} className="shrink-0 text-red-500" title={company.pipeline_error} />}
                  </div>
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
              <ScoreBreakdown breakdown={candidate?.score_breakdown} />
            </Panel>
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

function ScoreBreakdown({breakdown}) {
  if (!breakdown) return <div className="text-sm text-slate-500">Geen score beschikbaar</div>;

  // No-data geval: pipeline vond niets, breakdown bevat alleen een reden
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

  return (
    <div className="space-y-3 text-sm">
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
      <div>
        <div className="mb-1 text-xs text-slate-400 uppercase">Bron</div>
        <div>{breakdown.bron_type || "-"}{breakdown.n_bronnen > 1 ? ` (${breakdown.n_bronnen} bronnen)` : ""}</div>
      </div>
      {hasBonuses ? (
        <div className="rounded-md border border-emerald-200 bg-emerald-50 p-3">
          {Object.entries(bonuses).map(([key, value]) => (
            <div key={key} className="flex justify-between gap-3 text-emerald-800">
              <span>{key.replaceAll("_", " ")}</span>
              <span>+{pct(value)}%</span>
            </div>
          ))}
        </div>
      ) : null}
      {hasPenalties ? (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-3 text-amber-900">
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
    if (merged[key] != null && prev[key] !== merged[key]) {
      changedKeys.add(key);
    }
  }

  useEffect(() => {
    prevGegevensRef.current = {...merged};
  }, [gegevens]);

  return (
    <div className="flex flex-col rounded-lg border border-line bg-white shadow-sm max-h-[40vh] md:max-h-[85vh]">
      <div className="sticky top-0 z-10 rounded-t-lg border-b border-line bg-white p-4">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-semibold text-slate-700">Voortgang</span>
          <span className="font-bold text-etil">{pctVoortgang}%</span>
        </div>
        <div className="h-2 rounded-full bg-slate-200">
          <div
            className="h-2 rounded-full bg-etil transition-all duration-500"
            style={{width: `${pctVoortgang}%`}}
          />
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
                  <div
                    key={veld.key}
                    className={classNames(
                      "flex items-center gap-2 rounded px-2 py-1 text-sm",
                      isChanged && "field-pulse"
                    )}
                  >
                    {heeftWaarde
                      ? <span className="text-etil text-xs">✓</span>
                      : <span className="text-xs text-slate-300">○</span>
                    }
                    <span className={classNames("flex-1", heeftWaarde ? "text-slate-700" : "text-slate-400")}>
                      {veld.label}
                    </span>
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

const PERSONEEL_GROEPEN = [
  {
    label: "Dienstverband",
    velden: [
      {key: "eigen_personeel", label: "Eigen personeel"},
      {key: "uitzend", label: "Uitzendkrachten"},
      {key: "detachering", label: "Detachering"},
      {key: "wsw", label: "WSW"},
    ],
  },
  {
    label: "Geslacht",
    velden: [
      {key: "man", label: "Man"},
      {key: "vrouw", label: "Vrouw"},
    ],
  },
  {
    label: "Arbeidsduur",
    velden: [
      {key: "voltijd", label: "Voltijd"},
      {key: "deeltijd", label: "Deeltijd"},
    ],
  },
];

function PersoneelFormulier({wpTotaal, onSubmit, disabled}) {
  const [values, setValues] = useState({});
  const [activeGroep, setActiveGroep] = useState(0);

  const groep = PERSONEEL_GROEPEN[activeGroep];
  const som = groep.velden.reduce((s, v) => s + (Number(values[v.key]) || 0), 0);
  const resterend = wpTotaal - som;

  function update(key, val) {
    setValues((prev) => ({...prev, [key]: val}));
  }

  function submitGroep() {
    if (resterend !== 0) return;
    if (activeGroep < PERSONEEL_GROEPEN.length - 1) {
      setActiveGroep(activeGroep + 1);
    } else {
      onSubmit(values);
    }
  }

  return (
    <div className="rounded-lg border border-etil/30 bg-etil/5 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase text-etil">{groep.label}</span>
        <span className="text-xs text-slate-500">Totaal WP: <strong>{wpTotaal}</strong></span>
      </div>
      <div className="mb-2 grid gap-2" style={{gridTemplateColumns: `repeat(${groep.velden.length}, 1fr)`}}>
        {groep.velden.map((v) => (
          <div key={v.key}>
            <label className="mb-1 block text-xs text-slate-600">{v.label}</label>
            <input
              type="number"
              min="0"
              max={wpTotaal}
              className="focus-ring h-9 w-full rounded-md border border-line px-2 text-sm text-center"
              value={values[v.key] ?? ""}
              onChange={(e) => update(v.key, e.target.value)}
              disabled={disabled}
            />
          </div>
        ))}
      </div>
      <div className="flex items-center justify-between">
        <span className={classNames("text-xs font-medium", resterend === 0 ? "text-emerald-600" : resterend < 0 ? "text-red-600" : "text-amber-600")}>
          {resterend === 0 ? "✓ Som klopt" : resterend > 0 ? `Nog ${resterend} te verdelen` : `${Math.abs(resterend)} te veel`}
        </span>
        <button
          type="button"
          disabled={resterend !== 0 || disabled}
          onClick={submitGroep}
          className="focus-ring rounded-md bg-etil px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-40"
        >
          {activeGroep < PERSONEEL_GROEPEN.length - 1 ? "Volgende" : "Verstuur"}
        </button>
      </div>
      <div className="mt-2 flex gap-1">
        {PERSONEEL_GROEPEN.map((g, i) => (
          <div key={g.label} className={classNames("h-1 flex-1 rounded-full", i <= activeGroep ? "bg-etil" : "bg-slate-200")} />
        ))}
      </div>
    </div>
  );
}

function ChatForm({token}) {
  const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [typing, setTyping] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [gegevens, setGegevens] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    fetch(`${API_URL}/chat/${token}`)
      .then((r) => r.json())
      .then((data) => {
        if (data.status === "completed") {
          setDone(true);
        } else {
          setSession(data);
          const preFill = {};
          if (data.adres) preFill.adres = data.adres;
          if (data.pre_fill_wp) preFill.wp_totaal = data.pre_fill_wp;
          if (Object.keys(preFill).length > 0) setGegevens(preFill);
          if (data.messages && data.messages.length > 0) {
            setMessages(data.messages);
          } else {
            fetchReply([]);
          }
        }
      })
      .catch(() => setError("Chat-sessie niet gevonden of verlopen."));
  }, [token]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, typing]);

  async function fetchReply(msgs) {
    setTyping(true);
    try {
      const r = await fetch(`${API_URL}/chat/${token}/message`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({messages: msgs}),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "Fout in de chat.");
      const updated = [...msgs, {role: "assistant", content: data.reply}];
      setMessages(updated);
      if (data.done) setDone(true);
      if (data.gegevens) setGegevens(data.gegevens);
    } catch (err) {
      setMessages((prev) => [...prev, {role: "assistant", content: "Er is een fout opgetreden. Probeer het opnieuw."}]);
    } finally {
      setTyping(false);
    }
  }

  async function send(e) {
    if (e) e.preventDefault();
    const text = input.trim();
    if (!text || typing || done) return;
    setInput("");
    const updated = [...messages, {role: "user", content: text}];
    setMessages(updated);
    await fetchReply(updated);
  }

  if (error && !session) return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5] px-4">
      <div className="w-full max-w-md rounded-lg border border-red-200 bg-white p-8 text-center shadow-sm">
        <X className="mx-auto mb-3 text-red-500" size={32} />
        <p className="font-medium text-red-800">{error}</p>
      </div>
    </main>
  );

  if (done && !messages.length) return (
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

  if (!session && !done) return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5]">
      <div className="text-slate-500">Laden…</div>
    </main>
  );

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#eef2f5] px-4 py-8">
      <div className="mx-auto grid w-full max-w-[1000px] gap-4 md:grid-cols-[320px_1fr]">
        <OverzichtPanel gegevens={gegevens} />

        <div className="flex flex-col rounded-lg border border-line bg-white shadow-sm" style={{maxHeight: "90vh"}}>
          <div className="flex-shrink-0 rounded-t-lg bg-etil px-6 py-4">
            <div className="flex items-center gap-3">
              <ShieldCheck className="text-white/80" size={22} />
              <div>
                <div className="text-sm font-semibold text-white">Vestigingsregister AI</div>
                <div className="text-xs text-white/70">Etil Research Group — Provincie Limburg</div>
              </div>
            </div>
          </div>

          <div ref={scrollRef} className="flex flex-1 flex-col gap-3 overflow-y-auto p-4" style={{minHeight: "300px"}}>
            {messages.map((msg, i) => (
              <div key={i} className={classNames("flex gap-2", msg.role === "user" ? "flex-row-reverse" : "flex-row")}>
                <div className={classNames(
                  "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold",
                  msg.role === "user" ? "bg-slate-200 text-slate-600" : "bg-etil text-white"
                )}>
                  {msg.role === "user" ? "U" : "E"}
                </div>
                <div className={classNames(
                  "max-w-[80%] rounded-xl px-4 py-2.5 text-sm leading-relaxed",
                  msg.role === "user"
                    ? "rounded-br-sm bg-etil text-white"
                    : "rounded-bl-sm border border-line bg-panel text-slate-800"
                )} style={{whiteSpace: "pre-wrap"}}>
                  {msg.content.split(/(\*\*.*?\*\*)/).map((part, j) =>
                    part.startsWith("**") && part.endsWith("**")
                      ? <strong key={j}>{part.slice(2, -2)}</strong>
                      : part
                  )}
                </div>
              </div>
            ))}
            {typing && (
              <div className="flex gap-2">
                <div className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-etil text-xs font-bold text-white">E</div>
                <div className="flex items-center gap-1 rounded-xl rounded-bl-sm border border-line bg-panel px-4 py-3">
                  <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-etil" style={{animationDelay: "0ms"}} />
                  <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-etil" style={{animationDelay: "150ms"}} />
                  <span className="inline-block h-2 w-2 animate-bounce rounded-full bg-etil" style={{animationDelay: "300ms"}} />
                </div>
              </div>
            )}
            {done && messages.length > 0 && (
              <div className="mx-auto my-4 flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700">
                <Check size={16} /> Gegevens ontvangen — bedankt!
              </div>
            )}
          </div>

          {!done && (() => {
            const g = gegevens || {};
            const wpTotaal = typeof g.wp_totaal === "number" ? g.wp_totaal : null;
            const needsBreakdown = wpTotaal != null && (g.eigen_personeel == null || g.man == null || g.voltijd == null);

            return (
              <div className="flex-shrink-0 border-t border-line">
                {needsBreakdown && (
                  <div className="border-b border-line p-3">
                    <PersoneelFormulier
                      wpTotaal={wpTotaal}
                      disabled={typing}
                      onSubmit={async (vals) => {
                        const parts = Object.entries(vals)
                          .map(([k, v]) => {
                            const def = PERSONEEL_GROEPEN.flatMap((g) => g.velden).find((f) => f.key === k);
                            return `${def?.label || k}: ${v}`;
                          });
                        const text = parts.join(", ");
                        const updated = [...messages, {role: "user", content: text}];
                        setMessages(updated);
                        await fetchReply(updated);
                      }}
                    />
                  </div>
                )}
                <form onSubmit={send} className="flex gap-2 p-3">
                  <input
                    className="focus-ring h-11 flex-1 rounded-md border border-line px-3 text-sm"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Typ uw antwoord..."
                    disabled={typing}
                    autoFocus
                  />
                  <button
                    type="submit"
                    disabled={typing || !input.trim()}
                    className="focus-ring flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-md bg-etil text-white transition hover:opacity-90 disabled:opacity-40"
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="22" y1="2" x2="11" y2="13" />
                      <polygon points="22 2 15 22 11 13 2 9 22 2" />
                    </svg>
                  </button>
                </form>
              </div>
            );
          })()}

          <div className="flex-shrink-0 px-4 pb-3 text-center text-xs text-slate-400">
            Uw gegevens worden uitsluitend gebruikt voor het Vestigingsregister van Provincie Limburg.
          </div>
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
