import {useState} from "react";
import {Check} from "lucide-react";
import {Panel} from "../Panel.jsx";
import {KennisVeld} from "../KennisVeld.jsx";
import {IconButton} from "../IconButton.jsx";

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

export function WpUitsplitsing({wp_historie, api, batchId, companyId, onRefresh}) {
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
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{groep}</div>
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
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{groep}</div>
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
