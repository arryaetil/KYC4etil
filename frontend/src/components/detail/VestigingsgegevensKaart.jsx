import {useState} from "react";
import {Check} from "lucide-react";
import {Panel} from "../Panel.jsx";
import {Info} from "../Info.jsx";
import {IconButton} from "../IconButton.jsx";

export function VestigingsgegevensKaart({company, enrichment, api, batchId, onRefresh}) {
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
