import {ExternalLink, FileText} from "lucide-react";
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

  const bewijs = bewijsUrl(candidate);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b border-line px-4 py-3">
        <p className="text-xs text-slate-500">{brontypeLabel(candidate.brontype)}</p>
        <p className="mt-0.5 truncate text-sm font-medium text-ink" title={candidate.titel || candidate.url}>
          {candidate.titel || candidate.url}
        </p>
      </div>

      {bewijs.kanInbedden ? (
        <iframe
          key={bewijs.url}
          title={`Bewijs uit ${candidate.titel || candidate.url}`}
          src={bewijs.url}
          className="min-h-0 flex-1 border-0 bg-white"
        />
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-6">
          {candidate.bewijsfragment ? (
            <>
              <p className="mb-2 text-xs uppercase tracking-wide text-slate-400">
                Gevonden passage
              </p>
              <blockquote className="border-l-2 border-etil pl-4 text-base leading-relaxed text-ink">
                “{candidate.bewijsfragment}”
              </blockquote>
            </>
          ) : (
            <p className="text-sm text-slate-500">
              Deze bron bevat geen geëxtraheerde passage. Open de bron om zelf te beoordelen.
            </p>
          )}

          <a
            href={bewijs.url}
            target="_blank"
            rel="noreferrer"
            className="focus-ring mt-6 inline-flex items-center gap-1.5 rounded-md bg-ink px-3 py-2 text-sm text-white transition hover:opacity-90"
          >
            {candidate.bewijsfragment ? "Open bron op de bewijsplek" : "Bron openen"}
            <ExternalLink size={14} />
          </a>

          {candidate.bewijsfragment ? (
            <p className="mt-3 flex items-start gap-1.5 text-xs text-slate-500">
              <FileText size={13} className="mt-0.5 shrink-0" />
              <span>
                Webpagina’s openen in een nieuw tabblad; de browser scrollt zelf
                naar de passage en markeert die.
              </span>
            </p>
          ) : null}
        </div>
      )}
    </div>
  );
}
