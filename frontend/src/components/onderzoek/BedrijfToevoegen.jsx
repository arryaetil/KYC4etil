import {useState} from "react";
import {Plus, X} from "lucide-react";
import {Alert} from "../Alert.jsx";

const LEEG = {
  naam: "", vestigingsnummer: "", gemeente: "", adres: "",
  kvk_nummer: "", website_url: "", sbi_code: "", sbi_omschrijving: "",
};

const VELDEN = [
  {sleutel: "naam", label: "Organisatienaam", verplicht: true, breed: true},
  {sleutel: "vestigingsnummer", label: "Vestigingsnummer"},
  {sleutel: "kvk_nummer", label: "KvK-nummer"},
  {sleutel: "gemeente", label: "Gemeente"},
  {sleutel: "adres", label: "Adres"},
  {sleutel: "sbi_code", label: "SBI-code"},
  {sleutel: "sbi_omschrijving", label: "SBI-omschrijving"},
  {sleutel: "website_url", label: "Website", breed: true},
];

/**
 * Eén organisatie met de hand aan een lijst toevoegen.
 *
 * Alleen de naam is verplicht — de rest maakt het onderzoek beter maar mag de
 * reviewer niet ophouden. Vestigingsnummer en KvK staan vooraan omdat de
 * backend daarop herkent of deze vestiging al in de lijst staat; zonder die
 * twee valt hij terug op naam plus gemeente, en dan is "Jumbo" in Venlo iets
 * anders dan "Jumbo" in Roermond.
 */
export function BedrijfToevoegen({api, batchId, onToegevoegd}) {
  const [open, setOpen] = useState(false);
  const [waarden, setWaarden] = useState(LEEG);
  const [bezig, setBezig] = useState(false);
  const [error, setError] = useState("");
  const [melding, setMelding] = useState("");

  async function verstuur(event) {
    event.preventDefault();
    if (bezig || !waarden.naam.trim()) return;
    setBezig(true);
    setError("");
    setMelding("");
    try {
      const gevuld = Object.fromEntries(
        Object.entries(waarden)
          .map(([sleutel, waarde]) => [sleutel, waarde.trim() || null])
          .filter(([, waarde]) => waarde !== null),
      );
      const uitkomst = await api.voegBedrijfToe(batchId, gevuld);
      setWaarden(LEEG);
      setMelding(
        uitkomst.bestond_al
          ? `${gevuld.naam} stond al in de lijst${uitkomst.bijgewerkt ? " en is aangevuld" : ""}.`
          : `${gevuld.naam} toegevoegd.`,
      );
      onToegevoegd?.();
    } catch (err) {
      setError(err.message);
    } finally {
      setBezig(false);
    }
  }

  if (!open) {
    return (
      <div className="px-5 py-3">
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="focus-ring inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-sm text-ink transition hover:bg-panel"
        >
          <Plus size={14} />Organisatie toevoegen
        </button>
        {melding ? (
          <p className="mt-2 text-xs text-mist-65">{melding}</p>
        ) : null}
      </div>
    );
  }

  return (
    <form onSubmit={verstuur} className="border-y border-line bg-panel px-5 py-4">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-medium text-ink">Organisatie toevoegen</h3>
        <button
          type="button"
          onClick={() => { setOpen(false); setError(""); }}
          aria-label="Sluiten"
          className="focus-ring ml-auto rounded p-1 text-mist-65 transition hover:text-ink"
        >
          <X size={14} />
        </button>
      </div>

      {error ? <div className="mt-2"><Alert message={error} /></div> : null}

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        {VELDEN.map((veld) => (
          <label
            key={veld.sleutel}
            className={veld.breed ? "sm:col-span-2" : undefined}
          >
            <span className="block text-xs text-mist-65">
              {veld.label}{veld.verplicht ? " *" : ""}
            </span>
            <input
              value={waarden[veld.sleutel]}
              onChange={(e) => setWaarden({...waarden, [veld.sleutel]: e.target.value})}
              required={veld.verplicht}
              className="focus-ring mt-1 w-full rounded-md border border-line bg-white px-2 py-1.5 text-sm text-ink"
            />
          </label>
        ))}
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button
          type="submit"
          disabled={bezig || !waarden.naam.trim()}
          className="focus-ring inline-flex items-center gap-1.5 rounded-md bg-ink px-2.5 py-1.5 text-sm text-white transition hover:opacity-90 disabled:opacity-50"
        >
          <Plus size={14} />{bezig ? "Bezig…" : "Toevoegen"}
        </button>
        {melding ? <span className="text-xs text-mist-65">{melding}</span> : null}
      </div>
    </form>
  );
}
