import {useEffect, useState} from "react";
import {MessageSquare, Trash2} from "lucide-react";
import {formatMoment} from "../../lib/format.js";

/**
 * Een vrij tekstveld bij de organisatie waar een reviewer iets kwijt kan.
 *
 * Naast de vaste afwijs- en extractieredenen, niet in plaats daarvan. Die
 * keuzelijsten vangen op wát er mis was met een bron; ze vangen niet op dat een
 * vestiging is gefuseerd, dat het onderzoek steeds het concernverslag pakt, of
 * dat een hele sector een bron mist die de reviewer wél kent.
 *
 * Bewust geen categorieën: een keuzelijst kan alleen antwoorden op vragen die
 * we al hadden bedacht. De waarde zit in de stapel, en die wordt later door een
 * model gelezen om er terugkerende thema's uit te halen.
 */
export function Opmerkingen({api, companyId}) {
  const [items, setItems] = useState([]);
  const [tekst, setTekst] = useState("");
  const [bezig, setBezig] = useState(false);
  const [error, setError] = useState("");

  async function laad() {
    const data = await api.opmerkingen(companyId);
    setItems(data.items || []);
  }

  useEffect(() => {
    setTekst("");
    setError("");
    laad().catch((err) => setError(err.message));
  }, [companyId]);

  async function verstuur(event) {
    event.preventDefault();
    if (bezig || !tekst.trim()) return;
    setBezig(true);
    setError("");
    try {
      await api.voegOpmerkingToe(companyId, tekst.trim());
      setTekst("");
      await laad();
    } catch (err) {
      setError(err.message);
    } finally {
      setBezig(false);
    }
  }

  async function verwijder(id) {
    setError("");
    try {
      await api.verwijderOpmerking(id);
      await laad();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="mt-6 border-t border-line pt-4" aria-label="Opmerkingen">
      <h3 className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-slate-400">
        <MessageSquare size={12} />Opmerking
      </h3>

      {items.length ? (
        <ul className="mt-2 space-y-2">
          {items.map((item) => (
            <li key={item.id} className="rounded-md border border-line bg-panel px-3 py-2">
              <p className="max-w-[70ch] text-sm leading-relaxed text-ink">
                {item.tekst}
              </p>
              <p className="mt-1 flex items-center gap-2 text-xs text-slate-400">
                {item.geschreven_door || "onbekend"} · {formatMoment(item.created_at)}
                <button
                  type="button"
                  onClick={() => verwijder(item.id)}
                  aria-label="Opmerking verwijderen"
                  className="focus-ring rounded p-0.5 transition hover:text-red-700"
                >
                  <Trash2 size={12} />
                </button>
              </p>
            </li>
          ))}
        </ul>
      ) : null}

      <form onSubmit={verstuur} className="mt-2">
        <textarea
          value={tekst}
          onChange={(event) => setTekst(event.target.value)}
          rows={2}
          placeholder="Wat valt je op bij deze organisatie? Bijvoorbeeld: hij pakt steeds het concernverslag in plaats van deze locatie."
          className="focus-ring w-full rounded-md border border-line bg-white px-2.5 py-2 text-sm leading-relaxed text-ink placeholder:text-slate-400"
        />
        {error ? <p className="mt-1 text-xs text-red-700">{error}</p> : null}
        <button
          type="submit"
          disabled={bezig || !tekst.trim()}
          className="focus-ring mt-1.5 inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-sm text-ink transition hover:bg-panel disabled:opacity-50"
        >
          {bezig ? "Bezig…" : "Opmerking opslaan"}
        </button>
      </form>
    </section>
  );
}
