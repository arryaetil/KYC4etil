import {useState} from "react";
import {Check} from "lucide-react";
import {Panel} from "../Panel.jsx";
import {KennisVeld} from "../KennisVeld.jsx";
import {IconButton} from "../IconButton.jsx";

export function ContactgegevensKaart({enrichment, vastgoed: initVastgoed, api, batchId, companyId, onRefresh}) {
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
