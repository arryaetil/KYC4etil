import {useEffect, useState} from "react";
import {
  AlertTriangle, Check, ExternalLink, FileSearch, Globe2, Newspaper,
  Plus, RefreshCw, ShieldCheck, X,
} from "lucide-react";
import {Alert} from "./Alert.jsx";
import {IconButton} from "./IconButton.jsx";

function scoreLabel(score) {
  if (score == null) return "Niet gescoord";
  return `${Math.round(score * 100)}% rankingscore`;
}

function brontypeLabel(type) {
  return {
    officiele_website: "Officiële website",
    jaarverslag: "Jaarverslag",
    media: "Recente media",
    overheid: "Overheidsbron",
    sectorportaal: "Sectorbron",
    handmatig: "Handmatig toegevoegd",
  }[type] || type || "Openbare bron";
}

export function ResearchPanel({api, company, batchJaar}) {
  const [items, setItems] = useState([]);
  const [run, setRun] = useState(null);
  const [jaar, setJaar] = useState(batchJaar ? batchJaar - 1 : "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [manualOpen, setManualOpen] = useState(false);
  const [manualUrl, setManualUrl] = useState("");
  const [manualReason, setManualReason] = useState("");

  async function loadCandidates() {
    const data = await api.researchCandidates(company.company_id);
    setItems(data.items || []);
  }

  useEffect(() => {
    loadCandidates().catch((err) => setError(err.message));
  }, [company.company_id]);

  useEffect(() => {
    if (!run?.id || !["pending", "running"].includes(run.status)) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.researchRun(run.id);
        setRun(next);
        if (next.status === "completed" || next.status === "error") {
          setItems(next.kandidaten || []);
        }
      } catch (err) {
        setError(err.message);
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [run?.id, run?.status]);

  async function startResearch() {
    setBusy(true);
    setError("");
    try {
      const started = await api.startResearch(
        company.company_id,
        jaar === "" ? null : Number(jaar),
      );
      setRun({id: started.run_id, status: started.status, kandidaten: []});
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function review(candidateId, beslissing) {
    setError("");
    try {
      await api.reviewResearchCandidate(candidateId, beslissing);
      await loadCandidates();
    } catch (err) {
      setError(err.message);
    }
  }

  async function addManual(event) {
    event.preventDefault();
    setError("");
    try {
      await api.addManualResearchSource(company.company_id, {
        url: manualUrl,
        reden: manualReason || null,
      });
      setManualUrl("");
      setManualReason("");
      setManualOpen(false);
      await loadCandidates();
    } catch (err) {
      setError(err.message);
    }
  }

  const running = run && ["pending", "running"].includes(run.status);
  const visibleItems = run?.status === "completed" ? (run.kandidaten || []) : items;
  const accepted = visibleItems.find((candidate) => candidate.status === "geaccepteerd");

  return (
    <section aria-label={`Brononderzoek voor ${company.naam}`} className="bg-panel px-4 py-5 lg:px-6">
      {error ? <Alert message={error} /> : null}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-etil">Autonome research</p>
          <h3 className="mt-1 text-lg font-semibold text-ink">{company.naam}</h3>
          <p className="mt-1 max-w-3xl text-sm text-slate-600">
            De agent vergelijkt officiële pagina’s, documenten en recente media.
            Jij kiest welke bron als bewijs wordt gebruikt.
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-xs font-medium text-slate-700">
            Gewenst verslagjaar
            <input
              type="number"
              min="2000"
              max="2100"
              value={jaar}
              onChange={(event) => setJaar(event.target.value)}
              className="focus-ring mt-1 block h-10 w-32 rounded-md border border-line bg-white px-3 text-sm"
            />
          </label>
          <IconButton
            icon={running ? RefreshCw : FileSearch}
            variant="primary"
            onClick={startResearch}
            disabled={busy || running}
          >
            {running ? "Onderzoek loopt…" : "Bronnen zoeken"}
          </IconButton>
          <IconButton icon={Plus} onClick={() => setManualOpen((open) => !open)}>
            Bron toevoegen
          </IconButton>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-3">
        {[
          [Globe2, "Website", "Organisatie en officiële pagina’s"],
          [FileSearch, "Documenten", "Jaarstukken en openbare rapporten"],
          [Newspaper, "Media", "Recente en onafhankelijke berichtgeving"],
        ].map(([Icon, title, description]) => (
          <div key={title} className="flex items-start gap-2 rounded-md border border-line bg-white p-3">
            <Icon size={17} className="mt-0.5 shrink-0 text-etil" />
            <div>
              <div className="text-xs font-semibold text-ink">{title}</div>
              <div className="mt-0.5 text-xs text-slate-500">{description}</div>
            </div>
          </div>
        ))}
      </div>

      {accepted ? (
        <div className="mt-4 flex items-start gap-3 rounded-md border border-emerald-200 bg-emerald-50 p-4">
          <ShieldCheck size={20} className="mt-0.5 shrink-0 text-emerald-700" />
          <div>
            <p className="text-sm font-semibold text-emerald-900">Primaire bron gekozen</p>
            <a href={accepted.url} target="_blank" rel="noreferrer" className="focus-ring mt-1 inline-flex items-center gap-1 text-sm text-emerald-900 underline">
              {accepted.titel || accepted.url}<ExternalLink size={13} />
            </a>
          </div>
        </div>
      ) : null}

      {manualOpen ? (
        <form onSubmit={addManual} className="mt-4 flex flex-wrap items-end gap-2 border-t border-line pt-4">
          <label className="min-w-[280px] flex-1 text-xs font-medium text-slate-700">
            Bron-URL
            <input
              type="url"
              required
              value={manualUrl}
              onChange={(event) => setManualUrl(event.target.value)}
              className="focus-ring mt-1 h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
              placeholder="https://organisatie.nl/bron"
            />
          </label>
          <label className="min-w-[240px] flex-1 text-xs font-medium text-slate-700">
            Toelichting
            <input
              value={manualReason}
              onChange={(event) => setManualReason(event.target.value)}
              className="focus-ring mt-1 h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
              placeholder="Waarom is dit de juiste bron?"
            />
          </label>
          <IconButton icon={Check} variant="primary" type="submit">Opslaan</IconButton>
        </form>
      ) : null}

      {run?.status === "error" ? (
        <div className="mt-4 flex items-start gap-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          <AlertTriangle size={17} />
          <span>Het brononderzoek is mislukt: {run.fout || "onbekende fout"}</span>
        </div>
      ) : null}

      <div className="mt-4 overflow-hidden rounded-lg border border-line bg-white">
        {visibleItems.length ? (
          <ol className="divide-y divide-line">
            {visibleItems.map((candidate, index) => (
              <li key={candidate.id} className="p-4 lg:p-5">
                {(() => {
                  const bronreview = candidate.validaties?.intelligente_review;
                  return (
                <div className="flex flex-wrap items-start gap-4">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-ink text-sm font-semibold text-white">
                    {candidate.rang || index + 1}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-md border border-line bg-panel px-2 py-1 text-xs text-slate-700">
                        {brontypeLabel(candidate.brontype)}
                      </span>
                      <span className="text-xs font-medium text-etil">
                        {scoreLabel(candidate.ranking_score)}
                      </span>
                      {bronreview?.beslissing ? (
                        <span className="rounded-md border border-line bg-white px-2 py-1 text-xs font-semibold text-slate-700">
                          {bronreview.beslissing === "context_only"
                            ? "Alleen context"
                            : "Identiteit bevestigd"}
                        </span>
                      ) : null}
                      {candidate.status === "geaccepteerd" ? (
                        <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-800">
                          <Check size={12} />Geaccepteerd
                        </span>
                      ) : candidate.status === "afgewezen" ? (
                        <span className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-xs text-slate-600">
                          <X size={12} />Afgewezen
                        </span>
                      ) : null}
                    </div>
                    <a
                      href={candidate.url}
                      target="_blank"
                      rel="noreferrer"
                      className="focus-ring mt-2 inline-flex max-w-full items-center gap-1 font-semibold text-etil underline"
                    >
                      <span className="truncate">{candidate.titel || candidate.url}</span>
                      <ExternalLink size={14} className="shrink-0" />
                    </a>
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
                      {candidate.identity_class ? <span>Identiteit: {candidate.identity_class}</span> : null}
                      {candidate.verslagjaar ? <span>Verslagjaar: {candidate.verslagjaar}</span> : null}
                      {candidate.publicatiedatum ? <span>Gepubliceerd: {candidate.publicatiedatum}</span> : null}
                      {candidate.informatie_peilmoment ? <span>Peilmoment: {candidate.informatie_peilmoment}</span> : null}
                      {candidate.scope_class ? <span>Scope: {candidate.scope_class}</span> : null}
                    </div>
                    {candidate.bewijsfragment ? (
                      <blockquote className="mt-3 max-w-3xl text-sm leading-6 text-slate-700">
                        “{candidate.bewijsfragment}”
                        {candidate.bron_pagina ? ` — pagina ${candidate.bron_pagina}` : ""}
                      </blockquote>
                    ) : (
                      <p className="mt-3 text-sm text-slate-500">
                        Geen expliciet WP-fragment geëxtraheerd; beoordeel de bron zelf.
                      </p>
                    )}
                    {bronreview?.reden ? (
                      <div className="mt-3 flex items-start gap-2 rounded-md border border-sky-100 bg-sky-50 p-3 text-sm text-sky-950">
                        <ShieldCheck size={16} className="mt-0.5 shrink-0" />
                        <span><strong>Bronreview:</strong> {bronreview.reden}</span>
                      </div>
                    ) : null}
                    {candidate.waarschuwingen?.length ? (
                      <div className="mt-3 flex items-start gap-2 rounded-md bg-amber-50 p-2 text-xs font-medium text-amber-900">
                        <AlertTriangle size={14} className="shrink-0" />
                        <span>Controleer: {candidate.waarschuwingen.join(", ").replaceAll("_", " ")}</span>
                      </div>
                    ) : null}
                  </div>
                  {!["geaccepteerd", "afgewezen"].includes(candidate.status) ? (
                    <div className="flex w-full gap-2 sm:w-auto">
                      <IconButton
                        icon={Check}
                        variant="primary"
                        onClick={() => review(candidate.id, "accepteren")}
                      >
                        Accepteren
                      </IconButton>
                      <IconButton
                        icon={X}
                        onClick={() => review(candidate.id, "afwijzen")}
                      >
                        Afwijzen
                      </IconButton>
                    </div>
                  ) : null}
                </div>
                  );
                })()}
              </li>
            ))}
          </ol>
        ) : (
          <div className="p-6 text-sm text-slate-600">
            {running
              ? "De agent onderzoekt officiële websites, documenten en recente media."
              : "Nog geen bronkandidaten. Start een onderzoek of voeg een bekende bron toe."}
          </div>
        )}
      </div>
    </section>
  );
}
