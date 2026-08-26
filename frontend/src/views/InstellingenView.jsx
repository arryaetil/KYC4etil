import {useEffect, useState} from "react";
import {Plus, Trash2, UserPlus} from "lucide-react";
import {Alert} from "../components/Alert.jsx";

const LEGE_GEBRUIKER = {naam: "", email: "", rol: "reviewer", wachtwoord: ""};

/**
 * Eigen wachtwoord wijzigen, en voor een beheerder: collega toevoegen.
 *
 * Tot nu toe bestonden accounts alleen via `scripts/seed_users.py`, dat bij elke
 * run een nieuw willekeurig wachtwoord genereert. Een collega toevoegen
 * betekende een deploy en een script draaien, en niemand kon zijn eigen
 * wachtwoord veranderen.
 */
export function InstellingenView({api, user}) {
  const isBeheerder = user?.rol === "admin";
  const [huidig, setHuidig] = useState("");
  const [nieuw, setNieuw] = useState("");
  const [wwMelding, setWwMelding] = useState("");
  const [wwFout, setWwFout] = useState("");
  const [bezig, setBezig] = useState(false);

  const [gebruikers, setGebruikers] = useState([]);
  const [nieuweGebruiker, setNieuweGebruiker] = useState(LEGE_GEBRUIKER);
  const [gebruikerFout, setGebruikerFout] = useState("");
  const [gebruikerMelding, setGebruikerMelding] = useState("");
  const [formulierOpen, setFormulierOpen] = useState(false);

  async function laadGebruikers() {
    if (!isBeheerder) return;
    const data = await api.gebruikers();
    setGebruikers(data.items || []);
  }

  useEffect(() => {
    laadGebruikers().catch((err) => setGebruikerFout(err.message));
  }, [isBeheerder]);

  async function wijzigWachtwoord(event) {
    event.preventDefault();
    if (bezig) return;
    setBezig(true);
    setWwFout("");
    setWwMelding("");
    try {
      await api.wijzigWachtwoord(huidig, nieuw);
      setHuidig("");
      setNieuw("");
      setWwMelding("Je wachtwoord is gewijzigd.");
    } catch (err) {
      setWwFout(err.message);
    } finally {
      setBezig(false);
    }
  }

  async function voegGebruikerToe(event) {
    event.preventDefault();
    if (bezig) return;
    setBezig(true);
    setGebruikerFout("");
    setGebruikerMelding("");
    try {
      const aangemaakt = await api.maakGebruiker(nieuweGebruiker);
      setNieuweGebruiker(LEGE_GEBRUIKER);
      setFormulierOpen(false);
      setGebruikerMelding(
        `${aangemaakt.naam} kan nu inloggen met ${aangemaakt.email}.`,
      );
      await laadGebruikers();
    } catch (err) {
      setGebruikerFout(err.message);
    } finally {
      setBezig(false);
    }
  }

  async function verwijder(id, naam) {
    setGebruikerFout("");
    setGebruikerMelding("");
    try {
      await api.verwijderGebruiker(id);
      setGebruikerMelding(`${naam} heeft geen toegang meer.`);
      await laadGebruikers();
    } catch (err) {
      setGebruikerFout(err.message);
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl overflow-y-auto px-6 py-8">
      <h1 className="text-xl font-semibold text-ink">Instellingen</h1>

      <section className="mt-6" aria-label="Wachtwoord wijzigen">
        <h2 className="text-sm font-medium text-ink">Wachtwoord wijzigen</h2>
        <p className="mt-0.5 text-sm text-slate-500">
          Minstens tien tekens. Een lange zin is makkelijker te onthouden en
          moeilijker te raden dan een kort wachtwoord met tekens erin.
        </p>
        <form onSubmit={wijzigWachtwoord} className="mt-3 max-w-md space-y-3">
          <label className="block">
            <span className="block text-xs text-slate-500">Huidig wachtwoord</span>
            <input
              type="password"
              value={huidig}
              onChange={(e) => setHuidig(e.target.value)}
              required
              className="focus-ring mt-1 w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-sm text-ink"
            />
          </label>
          <label className="block">
            <span className="block text-xs text-slate-500">Nieuw wachtwoord</span>
            <input
              type="password"
              value={nieuw}
              onChange={(e) => setNieuw(e.target.value)}
              required
              minLength={10}
              className="focus-ring mt-1 w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-sm text-ink"
            />
          </label>
          {wwFout ? <Alert message={wwFout} /> : null}
          {wwMelding ? (
            <p className="text-sm text-emerald-800">{wwMelding}</p>
          ) : null}
          <button
            type="submit"
            disabled={bezig || !huidig || nieuw.length < 10}
            className="focus-ring rounded-md bg-ink px-3 py-1.5 text-sm text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {bezig ? "Bezig…" : "Wachtwoord wijzigen"}
          </button>
        </form>
      </section>

      {isBeheerder ? (
        <section className="mt-10 border-t border-line pt-6" aria-label="Gebruikers">
          <div className="flex items-center gap-3">
            <h2 className="text-sm font-medium text-ink">Gebruikers</h2>
            <button
              type="button"
              onClick={() => setFormulierOpen((open) => !open)}
              className="focus-ring ml-auto inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-sm text-ink transition hover:bg-panel"
            >
              <UserPlus size={14} />Gebruiker toevoegen
            </button>
          </div>

          {gebruikerFout ? (
            <div className="mt-3"><Alert message={gebruikerFout} /></div>
          ) : null}
          {gebruikerMelding ? (
            <p className="mt-3 text-sm text-emerald-800">{gebruikerMelding}</p>
          ) : null}

          {formulierOpen ? (
            <form
              onSubmit={voegGebruikerToe}
              className="mt-4 grid grid-cols-1 gap-3 rounded-md border border-line bg-panel p-4 sm:grid-cols-2"
            >
              {[
                ["naam", "Naam", "text"],
                ["email", "E-mailadres", "email"],
              ].map(([sleutel, label, type]) => (
                <label key={sleutel} className="block">
                  <span className="block text-xs text-slate-500">{label}</span>
                  <input
                    type={type}
                    value={nieuweGebruiker[sleutel]}
                    onChange={(e) => setNieuweGebruiker({
                      ...nieuweGebruiker, [sleutel]: e.target.value,
                    })}
                    required
                    className="focus-ring mt-1 w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-sm text-ink"
                  />
                </label>
              ))}
              <label className="block">
                <span className="block text-xs text-slate-500">Rol</span>
                <select
                  value={nieuweGebruiker.rol}
                  onChange={(e) => setNieuweGebruiker({
                    ...nieuweGebruiker, rol: e.target.value,
                  })}
                  className="focus-ring mt-1 w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-sm text-ink"
                >
                  <option value="reviewer">Reviewer — beoordeelt bronnen</option>
                  <option value="admin">Beheerder — beheert ook gebruikers</option>
                </select>
              </label>
              <label className="block">
                <span className="block text-xs text-slate-500">
                  Startwachtwoord (minstens 10 tekens)
                </span>
                {/* Zichtbaar en niet verborgen: de beheerder moet dit doorgeven
                    aan de collega, die het daarna zelf kan wijzigen. */}
                <input
                  type="text"
                  value={nieuweGebruiker.wachtwoord}
                  onChange={(e) => setNieuweGebruiker({
                    ...nieuweGebruiker, wachtwoord: e.target.value,
                  })}
                  required
                  minLength={10}
                  className="focus-ring mt-1 w-full rounded-md border border-line bg-white px-2.5 py-1.5 text-sm text-ink"
                />
              </label>
              <div className="sm:col-span-2">
                <button
                  type="submit"
                  disabled={bezig}
                  className="focus-ring inline-flex items-center gap-1.5 rounded-md bg-ink px-3 py-1.5 text-sm text-white transition hover:opacity-90 disabled:opacity-50"
                >
                  <Plus size={14} />{bezig ? "Bezig…" : "Aanmaken"}
                </button>
              </div>
            </form>
          ) : null}

          <ul className="mt-4 divide-y divide-line border-y border-line">
            {gebruikers.map((gebruiker) => (
              <li key={gebruiker.id} className="flex items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-ink">{gebruiker.naam}</p>
                  <p className="truncate text-xs text-slate-500">
                    {gebruiker.email} · {gebruiker.rol === "admin" ? "beheerder" : "reviewer"}
                  </p>
                </div>
                {gebruiker.id === user?.id ? (
                  <span className="text-xs text-slate-400">jij</span>
                ) : (
                  <button
                    type="button"
                    onClick={() => verwijder(gebruiker.id, gebruiker.naam)}
                    aria-label={`Toegang van ${gebruiker.naam} intrekken`}
                    className="focus-ring rounded p-1.5 text-slate-400 transition hover:text-red-700"
                  >
                    <Trash2 size={14} />
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
