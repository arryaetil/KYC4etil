import {useState} from "react";
import {Check} from "lucide-react";
import {Panel} from "../Panel.jsx";
import {KennisVeld} from "../KennisVeld.jsx";
import {IconButton} from "../IconButton.jsx";

const VASTGOED_VELDEN = [
  {key: "perceel_opp",         label: "Perceeloppervlakte",  unit: "m²", type: "number"},
  {key: "winkel_opp",          label: "Winkeloppervlakte",   unit: "m²", type: "number"},
  {key: "kantoor_opp",         label: "Kantooroppervlakte",  unit: "m²", type: "number"},
  {key: "bedrijfs_opp",        label: "Bedrijfsvloer",       unit: "m²", type: "number"},
  {key: "uitbreidingsruimte",  label: "Uitbreiding mogelijk",unit: "",   type: "bool"},
  {key: "seizoensverschillen", label: "Seizoensverschillen", unit: "",   type: "bool"},
];

export function VastgoedKaart({api, batchId, companyId, vastgoed: initVastgoed}) {
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
            <p className="mt-3 text-xs text-slate-500">
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
