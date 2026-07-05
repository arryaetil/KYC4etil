import {useEffect, useMemo, useState} from "react";
import {Check, Download, ListChecks, Mail, Phone, Trash2} from "lucide-react";
import {classNames} from "../lib/format.js";
import {Shell} from "../components/Shell.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {Alert} from "../components/Alert.jsx";
import {Metric} from "../components/Metric.jsx";

const BELLIJST_STATUS = {
  open: {label: "Open", cls: "bg-slate-100 text-slate-700"},
  gebeld: {label: "Gebeld", cls: "bg-blue-100 text-blue-800"},
  niet_bereikt: {label: "Niet bereikt", cls: "bg-amber-100 text-amber-800"},
  afgerond: {label: "Afgerond", cls: "bg-emerald-100 text-emerald-800"},
};

export function BellijstView({api, user, onLogout, batchId, openBatch}) {
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
          <select className="focus-ring h-10 rounded-md border border-line bg-white px-3 text-sm" value={filterStatus} onChange={(e) => setFilterStatus(e.target.value)} aria-label="Filter op status">
            <option value="">Alle statussen</option>
            {Object.entries(BELLIJST_STATUS).map(([v, {label}]) => <option key={v} value={v}>{label}</option>)}
          </select>
          <select className="focus-ring h-10 rounded-md border border-line bg-white px-3 text-sm" value={sortField} onChange={(e) => setSortField(e.target.value)} aria-label="Sorteren">
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
                    ) : <div className="mt-1 text-sm text-slate-500">Geen telefoonnummer</div>}
                    {item.email ? (
                      <a className="mt-1 inline-flex items-center gap-1 text-sm font-medium text-etil" href={`mailto:${item.email}`}>
                        <Mail size={14} />{item.email}
                      </a>
                    ) : null}
                  </div>
                  <span className={classNames("rounded-md px-2 py-1 text-xs font-semibold", cfg.cls)}>{cfg.label}</span>
                </div>
                {item.reden ? (
                  <div className="mb-3 rounded-md border border-line bg-panel px-3 py-2 text-sm text-slate-700">
                    <span className="font-semibold text-ink">Reden: </span>{item.reden}
                  </div>
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
