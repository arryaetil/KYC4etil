import {useEffect, useState} from "react";
import {Check, ListChecks, Plus, Trash2, X} from "lucide-react";
import {classNames} from "../lib/format.js";
import {Shell} from "../components/Shell.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {Alert} from "../components/Alert.jsx";

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

export function ChatTemplatesView({api, user, onLogout, openDashboard}) {
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
                    className="focus-ring rounded p-1 text-slate-500 hover:bg-red-50 hover:text-red-600"
                    onClick={(e) => { e.stopPropagation(); deleteTemplate(t); }}
                    disabled={deleting === t.id || t.is_default}
                    title={t.is_default ? "Standaard-template kan niet worden verwijderd" : "Verwijderen"}
                    aria-label={t.is_default ? "Standaard-template kan niet worden verwijderd" : "Template verwijderen"}
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
                  <label className="mb-1 block text-sm font-medium">Beschrijving <span className="font-normal text-slate-500">(optioneel)</span></label>
                  <input
                    className="focus-ring h-10 w-full rounded-md border border-line px-3 text-sm"
                    value={selected.beschrijving || ""}
                    onChange={(e) => setField("beschrijving", e.target.value)}
                    placeholder="Bijv. 'Volledig — alle velden'"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">
                    Aangepaste openingstekst <span className="font-normal text-slate-500">(optioneel — overschrijft standaard-opening)</span>
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
                  <span>Standaard-template <span className="text-slate-500">(automatisch gebruikt bij nieuwe uitnodigingen)</span></span>
                </label>
              </div>
            </div>

            {/* Velden configuratie */}
            <div className="rounded-lg border border-line bg-white p-5">
              <h3 className="mb-3 text-sm font-semibold">Welke velden uitvragen?</h3>
              <div className="space-y-5">
                {CHAT_VELDEN.map(({groep, velden}) => (
                  <div key={groep}>
                    <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{groep}</div>
                    <div className="space-y-1">
                      {velden.map(({key, label}) => {
                        const aan = (selected.veld_config || {})[key] !== false;
                        return (
                          <div key={key} className="flex items-center justify-between gap-3 rounded-md px-2 py-1.5 hover:bg-panel">
                            <span className={classNames("text-sm", !aan && "text-slate-400 line-through")}>{label}</span>
                            <button
                              onClick={() => toggleVeld(key)}
                              role="switch"
                              aria-checked={aan}
                              aria-label={label}
                              className={classNames(
                                "focus-ring relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full transition-colors",
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
                    <span className="w-5 shrink-0 text-center text-xs text-slate-500">{i + 1}.</span>
                    <input
                      className="focus-ring h-9 flex-1 rounded-md border border-line px-3 text-sm"
                      value={v}
                      onChange={(e) => setExtraVraag(i, e.target.value)}
                      placeholder="Stel een extra vraag…"
                    />
                    <button
                      onClick={() => removeExtraVraag(i)}
                      className="focus-ring rounded p-1 text-slate-500 hover:bg-red-50 hover:text-red-600"
                      aria-label="Vraag verwijderen"
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
          <div className="rounded-lg border border-dashed border-line bg-white p-8 text-center text-sm text-slate-500">
            Selecteer een template om te bewerken, of maak een nieuw template aan.
          </div>
        )}
      </div>
    </Shell>
  );
}
