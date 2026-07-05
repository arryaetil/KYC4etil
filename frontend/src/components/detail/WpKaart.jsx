import {useState} from "react";
import {AlertTriangle, Check} from "lucide-react";
import {pct} from "../../lib/format.js";
import {Panel} from "../Panel.jsx";
import {LabelBadge} from "../LabelBadge.jsx";
import {Progress} from "../Progress.jsx";
import {StatusPill} from "../StatusPill.jsx";
import {IconButton} from "../IconButton.jsx";

export function WpKaart({candidate, wp_historie, vorig_jaar, api, onRefresh}) {
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
          <div className="mt-0.5 text-xs text-slate-500">gevonden door agent</div>
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
          <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Historie</div>
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
