import {ExternalLink} from "lucide-react";
import {bewijsUrl} from "../../lib/evidenceLink.js";
import {brontypeLabel} from "../../lib/onderzoekLabels.js";

export function BewijsPaneel({candidate}) {
  if (!candidate) {
    return (
      <div className="flex h-full items-center justify-center px-6">
        <p className="max-w-xs text-center text-sm text-slate-500">
          Kies “Bewijs bekijken” bij een bron om de passage in het document te zien.
        </p>
      </div>
    );
  }

  // De ingesloten viewer haalt het document via de backend op en moet daarvoor
  // het token meesturen; een iframe kan zelf geen Authorization-header zetten.
  const bewijs = bewijsUrl(candidate, localStorage.getItem("token"));

  if (!bewijs.url) {
    return (
      <div className="flex h-full min-h-0 flex-col">
        <div className="border-b border-line px-4 py-3">
          <p className="text-xs text-slate-500">{brontypeLabel(candidate.brontype)}</p>
          <p className="mt-0.5 truncate text-sm font-medium text-ink">
            {candidate.titel || "Onbekende bron"}
          </p>
        </div>
        <div className="flex min-h-0 flex-1 items-center justify-center px-6">
          <p className="max-w-xs text-center text-sm text-slate-500">
            Voor deze bron is geen URL vastgelegd, dus er is niets om te openen.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b border-line px-4 py-3">
        <p className="text-xs text-slate-500">{brontypeLabel(candidate.brontype)}</p>
        <p className="mt-0.5 truncate text-sm font-medium text-ink" title={candidate.titel || candidate.url}>
          {candidate.titel || candidate.url}
        </p>
        {/* Ontsnappingsroute: rechtstreeks naar de bron, zonder te wachten
            op onze eigen leesweergave als die traag is of faalt. */}
        <a
          href={candidate.url}
          target="_blank"
          rel="noreferrer"
          className="focus-ring mt-1.5 inline-flex items-center gap-1.5 rounded text-xs text-slate-500 transition hover:text-ink"
        >
          Open origineel in nieuw tabblad
          <ExternalLink size={12} />
        </a>
      </div>

      <iframe
        key={bewijs.url}
        title={`Bewijs uit ${candidate.titel || candidate.url}`}
        src={bewijs.url}
        className="min-h-0 flex-1 border-0 bg-white"
      />
    </div>
  );
}
