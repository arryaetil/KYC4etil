# Onderzoekswerkbank frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** De frontend herbouwen tot twee modules (Onderzoek en Jaarverslagenmonitoring) met een drie-panelen werkbank waarin een onderzoeker bronkandidaten beoordeelt en met één handeling bij de exacte bewijsplek in de bron uitkomt.

**Architecture:** Nieuwe presentatielaag bovenop ongewijzigde bestaande endpoints. Eén vocabulairemodule (`lib/onderzoekLabels.js`) is de enige bron van waarheid voor labels en kleurtonen; alle componenten lezen daaruit. Legacy-views blijven als bestand bestaan maar worden onbereikbaar gemaakt in `App.jsx`.

**Tech Stack:** React 19, Vite 7, Tailwind 3, lucide-react, pdfjs-dist (al aanwezig). Vitest wordt toegevoegd voor de pure logicamodules.

## Global Constraints

- **Backend blijft ongewijzigd.** Geen enkele wijziging in `backend/`. Alle data komt uit bestaande endpoints in `frontend/src/api.js`.
- **Legacy-views worden verborgen, niet verwijderd.** De bestanden blijven staan; alleen de routes/navigatie ernaartoe verdwijnen uit `App.jsx`.
- **Geen rauwe enum-waarde en geen ruw scorepercentage in de UI.** Geen `exact_entity`, `vestiging`, `68.75% rankingscore`, en niets uit `LABELS` (`Eenduidig/Twijfelachtig/Onduidelijk`).
- **Kleurdiscipline:** standaard neutraal. Amber = "controleer dit". Rood = identiteitsmismatch of fout. Groen = uitsluitend een gekozen bron. **Geen groene "in orde"-badges** — de afwezigheid van een waarschuwing is het signaal.
- **Visuele taal (minimalistisch):** geen `shadow-sm` op nieuwe componenten (vlak). Scheiding primair via witruimte en `border-line`, niet via geneste kaders. Het bewijscitaat is het typografisch zwaarste element van een bronkaart (`text-base leading-relaxed text-ink`); metadata is `text-xs text-slate-500`. Bestaande kleurtokens gebruiken: `ink`, `line`, `panel`, `etil`.
- **Nederlandse domeintaal** in componentnamen, functienamen en commentaar, consistent met de rest van de codebase.
- Na elke taak moet `cd frontend && npm run build` slagen zonder fouten.
- Na elke taak: git commit met een beschrijvende Nederlandstalige boodschap.

---

## Task 1: Testopzet + vocabulaire- en bewijslogica

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.js`
- Create: `frontend/src/lib/onderzoekLabels.js`
- Create: `frontend/src/lib/evidenceLink.js`
- Test: `frontend/src/lib/onderzoekLabels.test.js`
- Test: `frontend/src/lib/evidenceLink.test.js`

**Interfaces:**
- Produces `onderzoekLabels.js`:
  - `TOON_STYLE: Record<"neutraal"|"aandacht"|"fout"|"gekozen", string>` — Tailwind-classes per toon
  - `organisatieStatus(company) -> {sleutel: string, label: string, toon: string}`
  - `identiteitLabel(identityClass) -> {label: string, toon: string}`
  - `bereikLabel(scopeClass) -> {label: string, toon: string}`
  - `brontypeLabel(brontype) -> string`
  - `bronwaarschuwingen(candidate) -> Array<{label: string, toon: string}>`
- Produces `evidenceLink.js`:
  - `bewijsUrl(candidate) -> {soort: "pdf"|"html"|null, url: string|null, kanInbedden: boolean}`

- [ ] **Step 1: Voeg vitest toe aan het project**

In `frontend/package.json`, voeg toe aan `devDependencies`:

```json
    "vitest": "^3.2.4"
```

En voeg toe aan `scripts`:

```json
    "test": "vitest run"
```

Maak `frontend/vitest.config.js`:

```js
import {defineConfig} from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.js"],
  },
});
```

Installeer: `cd frontend && npm install`

- [ ] **Step 2: Schrijf de falende tests voor het vocabulaire**

Maak `frontend/src/lib/onderzoekLabels.test.js`:

```js
import {describe, expect, it} from "vitest";
import {
  bereikLabel,
  bronwaarschuwingen,
  brontypeLabel,
  identiteitLabel,
  organisatieStatus,
} from "./onderzoekLabels.js";

describe("organisatieStatus", () => {
  it("meldt een niet-gestart onderzoek", () => {
    expect(organisatieStatus({research_status: "niet_gestart"}).label)
      .toBe("Nog niet onderzocht");
  });

  it("meldt een lopend onderzoek", () => {
    expect(organisatieStatus({research_status: "running"}).label)
      .toBe("Onderzoek loopt");
    expect(organisatieStatus({research_status: "pending"}).label)
      .toBe("Onderzoek loopt");
  });

  it("geeft een gekozen bron voorrang op de resultaatstatus", () => {
    const status = organisatieStatus({
      research_status: "completed",
      research_resultaat_status: "review_nodig",
      research_review_status: "geaccepteerd",
    });
    expect(status.label).toBe("Bron gekozen");
    expect(status.toon).toBe("gekozen");
  });

  it("meldt te beoordelen bij voorgestelde kandidaten", () => {
    const status = organisatieStatus({
      research_status: "completed",
      research_resultaat_status: "review_nodig",
    });
    expect(status.label).toBe("Te beoordelen");
    expect(status.sleutel).toBe("te_beoordelen");
  });

  it("meldt geen bron gevonden met aandacht-toon", () => {
    const status = organisatieStatus({
      research_status: "completed",
      research_resultaat_status: "niet_gevonden",
    });
    expect(status.label).toBe("Geen bron gevonden");
    expect(status.toon).toBe("aandacht");
  });

  it("meldt een mislukt onderzoek met fout-toon", () => {
    const status = organisatieStatus({research_status: "error"});
    expect(status.label).toBe("Mislukt");
    expect(status.toon).toBe("fout");
  });
});

describe("identiteitLabel", () => {
  it("vertaalt elke bekende klasse naar Nederlands", () => {
    expect(identiteitLabel("exact_entity").label).toBe("Dit bedrijf");
    expect(identiteitLabel("same_brand_or_group").label).toBe("Zelfde groep");
    expect(identiteitLabel("possible_match").label).toBe("Mogelijk ander bedrijf");
    expect(identiteitLabel("unknown").label).toBe("Mogelijk ander bedrijf");
    expect(identiteitLabel("mismatch").label).toBe("Ander bedrijf");
  });

  it("geeft een mismatch de fout-toon en een exacte match neutraal", () => {
    expect(identiteitLabel("mismatch").toon).toBe("fout");
    expect(identiteitLabel("exact_entity").toon).toBe("neutraal");
    expect(identiteitLabel("possible_match").toon).toBe("aandacht");
  });

  it("valt terug op onbekend zonder waarde", () => {
    expect(identiteitLabel(null).label).toBe("Mogelijk ander bedrijf");
  });
});

describe("bereikLabel", () => {
  it("vertaalt elke bekende scope naar Nederlands", () => {
    expect(bereikLabel("vestiging").label).toBe("Deze vestiging");
    expect(bereikLabel("limburg").label).toBe("Limburg");
    expect(bereikLabel("nederland").label).toBe("Heel Nederland");
    expect(bereikLabel("concern").label).toBe("Hele concern");
    expect(bereikLabel("unknown").label).toBe("Onbekend bereik");
  });

  it("markeert een te ruime scope als aandacht", () => {
    expect(bereikLabel("vestiging").toon).toBe("neutraal");
    expect(bereikLabel("limburg").toon).toBe("neutraal");
    expect(bereikLabel("nederland").toon).toBe("aandacht");
    expect(bereikLabel("concern").toon).toBe("aandacht");
  });
});

describe("brontypeLabel", () => {
  it("vertaalt bekende brontypes", () => {
    expect(brontypeLabel("officiele_website")).toBe("Officiële website");
    expect(brontypeLabel("jaarverslag")).toBe("Jaarverslag");
    expect(brontypeLabel("media")).toBe("Recente media");
    expect(brontypeLabel("handmatig")).toBe("Handmatig toegevoegd");
  });

  it("valt terug op een neutrale omschrijving", () => {
    expect(brontypeLabel(null)).toBe("Openbare bron");
  });
});

describe("bronwaarschuwingen", () => {
  it("waarschuwt bij een FTE-getal", () => {
    const labels = bronwaarschuwingen({eenheid: "fte", wp_gevonden: 47})
      .map((item) => item.label);
    expect(labels).toContain("FTE — geen WP");
  });

  it("waarschuwt bij een afwijkend verslagjaar", () => {
    const labels = bronwaarschuwingen({verslagjaar: 2024, gevraagd_jaar: 2025})
      .map((item) => item.label);
    expect(labels).toContain("Ander verslagjaar");
  });

  it("waarschuwt niet bij een gelijk verslagjaar", () => {
    const labels = bronwaarschuwingen({
      verslagjaar: 2025, gevraagd_jaar: 2025, wp_gevonden: 47,
      eenheid: "werkzame_personen",
    }).map((item) => item.label);
    expect(labels).toEqual([]);
  });

  it("waarschuwt als er geen getal is gevonden", () => {
    const labels = bronwaarschuwingen({wp_gevonden: null})
      .map((item) => item.label);
    expect(labels).toContain("Geen getal gevonden");
  });

  it("maakt technische waarschuwingen leesbaar", () => {
    const labels = bronwaarschuwingen({
      wp_gevonden: 47,
      eenheid: "werkzame_personen",
      waarschuwingen: ["geen_concreet_wp_bewijs"],
    }).map((item) => item.label);
    expect(labels).toContain("geen concreet wp bewijs");
  });
});
```

- [ ] **Step 3: Run de tests om te bevestigen dat ze falen**

Run: `cd frontend && npm test`
Expected: FAIL — `Failed to resolve import "./onderzoekLabels.js"`

- [ ] **Step 4: Implementeer het vocabulaire**

Maak `frontend/src/lib/onderzoekLabels.js`:

```js
/**
 * Eén bron van waarheid voor alle labels en kleurtonen in de onderzoeksmodule.
 *
 * Kleurdiscipline: standaard neutraal. Amber ("aandacht") betekent uitsluitend
 * "controleer dit", rood ("fout") uitsluitend een identiteitsmismatch of een
 * mislukking, groen ("gekozen") uitsluitend een gekozen bron. Er bestaat
 * bewust geen groene "in orde"-toon: de afwezigheid van een waarschuwing is
 * het signaal.
 */

export const TOON_STYLE = {
  neutraal: "border-line bg-white text-slate-600",
  aandacht: "border-amber-200 bg-amber-50 text-amber-900",
  fout: "border-red-200 bg-red-50 text-red-800",
  gekozen: "border-emerald-200 bg-emerald-50 text-emerald-900",
};

const IDENTITEIT = {
  exact_entity: {label: "Dit bedrijf", toon: "neutraal"},
  same_brand_or_group: {label: "Zelfde groep", toon: "aandacht"},
  possible_match: {label: "Mogelijk ander bedrijf", toon: "aandacht"},
  unknown: {label: "Mogelijk ander bedrijf", toon: "aandacht"},
  mismatch: {label: "Ander bedrijf", toon: "fout"},
};

const BEREIK = {
  vestiging: {label: "Deze vestiging", toon: "neutraal"},
  limburg: {label: "Limburg", toon: "neutraal"},
  nederland: {label: "Heel Nederland", toon: "aandacht"},
  concern: {label: "Hele concern", toon: "aandacht"},
  unknown: {label: "Onbekend bereik", toon: "aandacht"},
};

const BRONTYPE = {
  officiele_website: "Officiële website",
  jaarverslag: "Jaarverslag",
  media: "Recente media",
  overheid: "Overheidsbron",
  sectorportaal: "Sectorbron",
  handmatig: "Handmatig toegevoegd",
};

export function organisatieStatus(company) {
  const status = company?.research_status;
  if (status === "error") {
    return {sleutel: "mislukt", label: "Mislukt", toon: "fout"};
  }
  if (status === "running" || status === "pending") {
    return {sleutel: "loopt", label: "Onderzoek loopt", toon: "neutraal"};
  }
  if (!status || status === "niet_gestart") {
    return {
      sleutel: "niet_onderzocht",
      label: "Nog niet onderzocht",
      toon: "neutraal",
    };
  }
  if (company.research_review_status === "geaccepteerd") {
    return {sleutel: "gekozen", label: "Bron gekozen", toon: "gekozen"};
  }
  if (company.research_resultaat_status === "niet_gevonden") {
    return {
      sleutel: "niet_gevonden",
      label: "Geen bron gevonden",
      toon: "aandacht",
    };
  }
  if (company.research_resultaat_status === "review_nodig") {
    return {sleutel: "te_beoordelen", label: "Te beoordelen", toon: "neutraal"};
  }
  return {sleutel: "afgerond", label: "Onderzoek afgerond", toon: "neutraal"};
}

export function identiteitLabel(identityClass) {
  return IDENTITEIT[identityClass] || IDENTITEIT.unknown;
}

export function bereikLabel(scopeClass) {
  return BEREIK[scopeClass] || BEREIK.unknown;
}

export function brontypeLabel(brontype) {
  return BRONTYPE[brontype] || "Openbare bron";
}

export function bronwaarschuwingen(candidate) {
  if (!candidate) return [];
  const items = [];
  if (candidate.eenheid === "fte") {
    items.push({label: "FTE — geen WP", toon: "aandacht"});
  }
  if (
    candidate.gevraagd_jaar != null
    && candidate.verslagjaar != null
    && candidate.gevraagd_jaar !== candidate.verslagjaar
  ) {
    items.push({label: "Ander verslagjaar", toon: "aandacht"});
  }
  if (candidate.wp_gevonden == null) {
    items.push({label: "Geen getal gevonden", toon: "aandacht"});
  }
  for (const waarschuwing of candidate.waarschuwingen || []) {
    items.push({
      label: String(waarschuwing).replaceAll("_", " "),
      toon: "aandacht",
    });
  }
  return items;
}
```

- [ ] **Step 5: Run de vocabulairetests om te bevestigen dat ze slagen**

Run: `cd frontend && npm test`
Expected: alle tests in `onderzoekLabels.test.js` PASS.

- [ ] **Step 6: Schrijf de falende tests voor de bewijs-URL's**

Maak `frontend/src/lib/evidenceLink.test.js`:

```js
import {describe, expect, it} from "vitest";
import {bewijsUrl} from "./evidenceLink.js";

describe("bewijsUrl", () => {
  it("geeft niets terug zonder bron", () => {
    expect(bewijsUrl(null)).toEqual({soort: null, url: null, kanInbedden: false});
    expect(bewijsUrl({url: ""})).toEqual({soort: null, url: null, kanInbedden: false});
  });

  it("bouwt een insluitbare pdf.js-URL met pagina en zoekterm", () => {
    const resultaat = bewijsUrl({
      url: "https://example.test/jaarverslag.pdf",
      bron_pagina: 14,
      bewijsfragment: "47 medewerkers in dienst",
    });
    expect(resultaat.soort).toBe("pdf");
    expect(resultaat.kanInbedden).toBe(true);
    expect(resultaat.url).toContain("/pdfjs/viewer.html");
    expect(resultaat.url).toContain("page=14");
    expect(resultaat.url).toContain("search=");
  });

  it("herkent een pdf ook met queryparameters achter de extensie", () => {
    expect(bewijsUrl({url: "https://example.test/verslag.pdf?v=2"}).soort)
      .toBe("pdf");
  });

  it("bouwt voor html een tekstfragment dat niet insluitbaar is", () => {
    const resultaat = bewijsUrl({
      url: "https://example.test/over-ons",
      bewijsfragment: "47 medewerkers in dienst",
    });
    expect(resultaat.soort).toBe("html");
    expect(resultaat.kanInbedden).toBe(false);
    expect(resultaat.url).toContain("#:~:text=");
  });

  it("codeert koppeltekens en kommas die het tekstfragment zouden breken", () => {
    const resultaat = bewijsUrl({
      url: "https://example.test/over-ons",
      bewijsfragment: "ruim 47 medewerkers, full-time in dienst",
    });
    expect(resultaat.url).not.toMatch(/text=[^#]*[,-]/);
    expect(resultaat.url).toContain("%2D");
    expect(resultaat.url).toContain("%2C");
  });

  it("kort een lang citaat in op een woordgrens", () => {
    const lang = "Wij zijn een organisatie die inmiddels is uitgegroeid tot een "
      + "van de grootste werkgevers van de regio met veel medewerkers";
    const resultaat = bewijsUrl({
      url: "https://example.test/over-ons",
      bewijsfragment: lang,
    });
    const fragment = decodeURIComponent(
      resultaat.url.split("#:~:text=")[1].replaceAll("%2D", "-"),
    );
    expect(fragment.length).toBeLessThanOrEqual(60);
    expect(lang.startsWith(fragment)).toBe(true);
    expect(fragment.endsWith(" ")).toBe(false);
  });

  it("valt zonder citaat terug op de kale bron-URL", () => {
    const resultaat = bewijsUrl({url: "https://example.test/over-ons"});
    expect(resultaat.soort).toBe("html");
    expect(resultaat.url).toBe("https://example.test/over-ons");
  });
});
```

- [ ] **Step 7: Run de tests om te bevestigen dat ze falen**

Run: `cd frontend && npm test`
Expected: FAIL — `Failed to resolve import "./evidenceLink.js"`

- [ ] **Step 8: Implementeer de bewijs-URL-logica**

Maak `frontend/src/lib/evidenceLink.js`:

```js
import {buildPdfViewerUrl} from "./pdfViewerLink.js";

const MAX_FRAGMENT_LENGTE = 60;

function isPdf(url) {
  try {
    return new URL(url).pathname.toLowerCase().endsWith(".pdf");
  } catch {
    return url.toLowerCase().includes(".pdf");
  }
}

/**
 * Kort het citaat in tot een korte, distinctieve passage. Te lange fragmenten
 * matchen vaker niet, omdat de gerenderde pagina subtiel kan afwijken van de
 * tekst die de agent extraheerde.
 */
function kortFragment(citaat) {
  const schoon = citaat.trim().replace(/\s+/g, " ");
  if (schoon.length <= MAX_FRAGMENT_LENGTE) return schoon;
  const afgekapt = schoon.slice(0, MAX_FRAGMENT_LENGTE);
  const laatsteSpatie = afgekapt.lastIndexOf(" ");
  return (laatsteSpatie > 0 ? afgekapt.slice(0, laatsteSpatie) : afgekapt).trim();
}

/**
 * Codeert een tekstfragment voor een `#:~:text=`-directive. Komma's scheiden
 * de onderdelen van zo'n directive en koppeltekens markeren prefix/suffix,
 * dus die moeten percent-gecodeerd worden. encodeURIComponent laat het
 * koppelteken ongemoeid, vandaar de extra vervanging.
 */
function codeerFragment(tekst) {
  return encodeURIComponent(tekst).replaceAll("-", "%2D");
}

/**
 * Bepaalt hoe het bewijs van een bronkandidaat getoond kan worden.
 *
 * PDF's gaan door de meegeleverde pdf.js-viewer en kunnen daardoor ingesloten
 * worden getoond op de juiste pagina, met highlight. HTML-bronnen kunnen dat
 * niet: browsers passen tekstfragmenten niet toe binnen een iframe, en een
 * cross-origin pagina kan niet door ons worden gemanipuleerd. Voor HTML wordt
 * daarom een tekstfragment-URL gebouwd die in een nieuw tabblad geopend moet
 * worden, waar de browser zelf naar het citaat scrollt en het markeert.
 */
export function bewijsUrl(candidate) {
  const bron = candidate?.url;
  if (!bron) return {soort: null, url: null, kanInbedden: false};

  if (isPdf(bron)) {
    return {
      soort: "pdf",
      url: buildPdfViewerUrl({
        bronUrl: bron,
        pagina: candidate.bron_pagina,
        citaat: candidate.bewijsfragment,
      }),
      kanInbedden: true,
    };
  }

  const citaat = candidate.bewijsfragment?.trim();
  if (!citaat) return {soort: "html", url: bron, kanInbedden: false};

  const basis = bron.split("#")[0];
  return {
    soort: "html",
    url: `${basis}#:~:text=${codeerFragment(kortFragment(citaat))}`,
    kanInbedden: false,
  };
}
```

- [ ] **Step 9: Run alle tests**

Run: `cd frontend && npm test`
Expected: alle tests in beide bestanden PASS.

- [ ] **Step 10: Verifieer dat de build nog slaagt**

Run: `cd frontend && npm run build`
Expected: build slaagt zonder fouten.

- [ ] **Step 11: Commit**

```bash
cd /Users/arryawillems/Desktop/Projects/KYC4etil
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.js frontend/src/lib/onderzoekLabels.js frontend/src/lib/onderzoekLabels.test.js frontend/src/lib/evidenceLink.js frontend/src/lib/evidenceLink.test.js
git commit -m "feat(frontend): vocabulairemodule en bewijs-deeplinking met vitest-dekking"
```

---

## Task 2: AppShell met tweemodule-navigatie

**Files:**
- Create: `frontend/src/components/AppShell.jsx`
- Modify: `frontend/src/App.jsx`

**Interfaces:**
- Consumes: niets uit Task 1.
- Produces: `<AppShell user module onModule onLogout>{children}</AppShell>` waarbij `module` `"onderzoek" | "monitoring"` is en `onModule(naam)` de module wisselt.

- [ ] **Step 1: Maak de AppShell**

Maak `frontend/src/components/AppShell.jsx`:

```jsx
import {LogOut} from "lucide-react";
import {classNames} from "../lib/format.js";

const MODULES = [
  ["onderzoek", "Onderzoek"],
  ["monitoring", "Jaarverslagenmonitoring"],
];

export function AppShell({user, module, onModule, onLogout, children}) {
  return (
    <div className="flex min-h-screen flex-col bg-white">
      <header className="border-b border-line">
        <div className="flex items-center justify-between gap-6 px-6 py-3">
          <div className="flex items-center gap-8">
            <div className="flex flex-col leading-none">
              <span className="text-lg font-black italic tracking-tight text-[#C8102E]">
                Etil
              </span>
              <span className="text-[9px] font-medium tracking-wide text-slate-400">
                research group
              </span>
            </div>
            <nav className="flex items-center gap-1" aria-label="Modules">
              {MODULES.map(([sleutel, label]) => (
                <button
                  key={sleutel}
                  type="button"
                  aria-current={module === sleutel ? "page" : undefined}
                  onClick={() => onModule(sleutel)}
                  className={classNames(
                    "focus-ring rounded-md px-3 py-1.5 text-sm transition",
                    module === sleutel
                      ? "bg-panel font-semibold text-ink"
                      : "text-slate-500 hover:text-ink",
                  )}
                >
                  {label}
                </button>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-slate-500 sm:block">
              {user?.naam}
            </span>
            <button
              type="button"
              onClick={onLogout}
              title="Uitloggen"
              aria-label="Uitloggen"
              className="focus-ring rounded-md p-2 text-slate-400 transition hover:bg-panel hover:text-ink"
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </header>
      <main className="flex min-h-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
```

- [ ] **Step 2: Herschrijf de routing naar twee modules**

Vervang de volledige inhoud van `frontend/src/App.jsx` door:

```jsx
import {useMemo, useState} from "react";
import {createApi} from "./api.js";
import {Login} from "./views/Login.jsx";
import {ChatForm} from "./views/ChatForm.jsx";
import {AppShell} from "./components/AppShell.jsx";
import {OnderzoekView} from "./views/OnderzoekView.jsx";
import {MonitoringView} from "./views/MonitoringView.jsx";

export default function App() {
  // Publieke chat-route — afhandelen vóór de auth-flow, want deze link wordt
  // buiten de applicatie om gedeeld.
  const chatToken = new URLSearchParams(window.location.search).get("chat");
  if (chatToken) return <ChatForm token={chatToken} />;

  const [token, setToken] = useState(() => localStorage.getItem("token") || "");
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  });
  const [module, setModule] = useState("onderzoek");

  const api = useMemo(() => createApi(token, () => logout()), [token]);

  function login(nextToken, nextUser) {
    localStorage.setItem("token", nextToken);
    localStorage.setItem("user", JSON.stringify(nextUser));
    setToken(nextToken);
    setUser(nextUser);
  }

  function logout() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
    setToken("");
    setUser(null);
    setModule("onderzoek");
  }

  if (!token) return <Login api={api} onLogin={login} />;

  return (
    <AppShell user={user} module={module} onModule={setModule} onLogout={logout}>
      {module === "onderzoek"
        ? <OnderzoekView api={api} />
        : <MonitoringView api={api} />}
    </AppShell>
  );
}
```

- [ ] **Step 3: Maak een tijdelijke OnderzoekView zodat de app bouwt**

`OnderzoekView` wordt in Task 3 en 4 opgebouwd. Maak nu `frontend/src/views/OnderzoekView.jsx` met een minimale, werkende versie:

```jsx
export function OnderzoekView() {
  return (
    <div className="px-6 py-8 text-sm text-slate-500">
      Onderzoeksmodule wordt opgebouwd.
    </div>
  );
}
```

- [ ] **Step 4: Pas MonitoringView aan op de nieuwe props**

`MonitoringView` krijgt nu alleen nog `api` en zit al binnen `AppShell`, dus zijn
eigen `Shell` (met een tweede header) moet weg. Task 8 herbouwt deze view
volledig; dit is een tussenstap zodat de app blijft werken.

Maak in `frontend/src/views/MonitoringView.jsx` precies drie bewerkingen.

**(a)** Vervang de signatuur:

```jsx
export function MonitoringView({api, user, onLogout, openDashboard, openCompany}) {
```

door:

```jsx
export function MonitoringView({api}) {
```

**(b)** Vervang de opening van de return — dit blok:

```jsx
    <Shell
      user={user}
      onLogout={onLogout}
      title="Bronnenmonitoring"
      actions={
        <>
          <IconButton icon={ListChecks} onClick={openDashboard}>Dashboard</IconButton>
          {batch ? (
            <IconButton icon={RefreshCw} variant="primary" onClick={nuControleren} disabled={busy}>
              {busy ? "Bezig…" : "Nu controleren"}
            </IconButton>
          ) : null}
        </>
      }
    >
```

door:

```jsx
    <div className="px-6 py-6">
      {batch ? (
        <div className="mb-4 flex justify-end">
          <IconButton icon={RefreshCw} onClick={nuControleren} disabled={busy}>
            {busy ? "Bezig…" : "Nu controleren"}
          </IconButton>
        </div>
      ) : null}
```

**(c)** Vervang de afsluiting `</Shell>` door `</div>`.

Verwijder tot slot de nu ongebruikte imports `Shell` en `ListChecks`, en
verwijder op de tabelrij het attribuut `onClick={() => openCompany(batch.id, company.company_id)}`
plus de bijbehorende `cursor-pointer`-class (die rij wordt in Task 8 herbouwd).

- [ ] **Step 5: Verifieer build en tests**

Run: `cd frontend && npm run build && npm test`
Expected: build slaagt, tests uit Task 1 blijven groen.

- [ ] **Step 6: Visuele controle**

Run: `cd frontend && npm run dev`, log in, en controleer:
- De header toont exact twee navigatie-items: "Onderzoek" en "Jaarverslagenmonitoring".
- Er is geen enkele knop meer naar Dashboard, Jaarverslagen, Chat-templates, Bellijst of Chat-sessies.
- Wisselen tussen de twee modules werkt.

- [ ] **Step 7: Commit**

```bash
cd /Users/arryawillems/Desktop/Projects/KYC4etil
git add frontend/src/components/AppShell.jsx frontend/src/App.jsx frontend/src/views/OnderzoekView.jsx frontend/src/views/MonitoringView.jsx
git commit -m "feat(frontend): tweemodule-navigatie, legacy-views niet langer bereikbaar"
```

---

## Task 3: Batchoverzicht

**Files:**
- Create: `frontend/src/views/BatchesView.jsx`
- Modify: `frontend/src/views/OnderzoekView.jsx`

**Interfaces:**
- Consumes: `organisatieStatus` is hier níet nodig; wel `api.batches()`, `api.uploadBatch(file, naam, jaar)`, `api.runBatch(id)`, `api.cancelBatch(id)`, `api.deleteBatch(id)`, `api.download(path, filename)`.
- Produces: `<BatchesView api onOpenBatch />` waarbij `onOpenBatch(batchId)` de werkbank opent.
- Produces: `OnderzoekView` houdt `batchId` in state; `null` toont `BatchesView`.

- [ ] **Step 1: Maak het batchoverzicht**

Maak `frontend/src/views/BatchesView.jsx`:

```jsx
import {useEffect, useRef, useState} from "react";
import {FileDown, FileUp, Play, Square, Trash2} from "lucide-react";
import {Alert} from "../components/Alert.jsx";
import {IconButton} from "../components/IconButton.jsx";

function formatDatum(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("nl-NL", {
    day: "numeric", month: "short", year: "numeric",
  });
}

export function BatchesView({api, onOpenBatch}) {
  const fileRef = useRef(null);
  const [batches, setBatches] = useState([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const lijst = await api.batches();
    setBatches(lijst.sort(
      (a, b) => (b.created_at || "").localeCompare(a.created_at || ""),
    ));
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
  }, []);

  const heeftLopende = batches.some((batch) => batch.status === "running");

  useEffect(() => {
    if (!heeftLopende) return undefined;
    const timer = window.setInterval(() => load().catch(() => {}), 10000);
    return () => window.clearInterval(timer);
  }, [heeftLopende]);

  async function upload(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const naam = file.name.replace(/\.[^.]+$/, "");
      const created = await api.uploadBatch(file, naam, new Date().getFullYear());
      await load();
      onOpenBatch(created.batch_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      event.target.value = "";
    }
  }

  async function voerUit(actie) {
    setBusy(true);
    setError("");
    try {
      await actie();
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-6 py-8">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink">Onderzoek</h1>
          <p className="mt-1 text-sm text-slate-500">
            Kies een populatie om bronnen voor te beoordelen.
          </p>
        </div>
        <input
          ref={fileRef}
          type="file"
          accept=".csv,text/csv"
          className="hidden"
          onChange={upload}
        />
        <IconButton
          icon={FileUp}
          variant="primary"
          onClick={() => fileRef.current?.click()}
          disabled={busy}
        >
          Lijst uploaden
        </IconButton>
      </div>

      {error ? <Alert message={error} /> : null}

      <ul className="divide-y divide-line border-y border-line">
        {batches.map((batch) => (
          <li key={batch.id} className="flex items-center gap-4 py-4">
            <div className="min-w-0 flex-1">
              <button
                type="button"
                onClick={() => onOpenBatch(batch.id)}
                className="focus-ring rounded text-left font-medium text-ink hover:underline"
              >
                {batch.naam || batch.id}
              </button>
              <div className="mt-0.5 text-xs text-slate-500">
                {batch.jaar} · {formatDatum(batch.created_at)}
                {batch.geupload_door_naam ? ` · ${batch.geupload_door_naam}` : ""}
              </div>
            </div>
            <div className="w-32 shrink-0 text-right text-xs tabular-nums text-slate-500">
              {batch.verwerkt || 0} / {batch.totaal || 0}
            </div>
            <div className="flex shrink-0 items-center gap-1">
              {batch.status === "running" ? (
                <IconButton
                  icon={Square}
                  variant="quiet"
                  disabled={busy}
                  onClick={() => voerUit(() => api.cancelBatch(batch.id))}
                >
                  Stoppen
                </IconButton>
              ) : (
                <IconButton
                  icon={Play}
                  variant="quiet"
                  disabled={busy}
                  onClick={() => voerUit(() => api.runBatch(batch.id))}
                >
                  Onderzoeken
                </IconButton>
              )}
              <IconButton
                icon={FileDown}
                variant="quiet"
                title="Exporteren"
                onClick={() => api.download(
                  `/batches/${batch.id}/export.xlsx`, "export.xlsx",
                )}
              />
              <IconButton
                icon={Trash2}
                variant="quiet"
                title="Verwijderen"
                disabled={busy || batch.status === "running"}
                onClick={() => {
                  if (!window.confirm(`Lijst "${batch.naam}" verwijderen?`)) return;
                  voerUit(() => api.deleteBatch(batch.id));
                }}
              />
            </div>
          </li>
        ))}
        {!batches.length ? (
          <li className="py-12 text-center text-sm text-slate-500">
            Nog geen lijsten. Upload een CSV om te beginnen.
          </li>
        ) : null}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: Laat OnderzoekView tussen overzicht en werkbank schakelen**

Vervang de inhoud van `frontend/src/views/OnderzoekView.jsx` door:

```jsx
import {useState} from "react";
import {BatchesView} from "./BatchesView.jsx";

export function OnderzoekView({api}) {
  const [batchId, setBatchId] = useState(null);

  if (!batchId) return <BatchesView api={api} onOpenBatch={setBatchId} />;

  return (
    <div className="px-6 py-8 text-sm text-slate-500">
      Werkbank voor batch {batchId} wordt opgebouwd.
      <button
        type="button"
        className="focus-ring ml-2 rounded underline"
        onClick={() => setBatchId(null)}
      >
        Terug
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Verifieer build en tests**

Run: `cd frontend && npm run build && npm test`
Expected: build slaagt, tests groen.

- [ ] **Step 4: Visuele controle**

Run: `cd frontend && npm run dev` en controleer:
- Het batchoverzicht toont de bestaande lijsten met voortgang en datum.
- Klikken op een naam opent de (nog lege) werkbank; "Terug" keert terug.
- Uploaden, onderzoeken starten, exporteren en verwijderen werken.
- Er is nergens een legacy-label ("Eenduidig/Twijfelachtig/Onduidelijk") zichtbaar.

- [ ] **Step 5: Commit**

```bash
cd /Users/arryawillems/Desktop/Projects/KYC4etil
git add frontend/src/views/BatchesView.jsx frontend/src/views/OnderzoekView.jsx
git commit -m "feat(frontend): rustig batchoverzicht als startpunt van de onderzoeksmodule"
```

---

## Task 4: Werkbanklayout en organisatielijst

**Files:**
- Create: `frontend/src/components/onderzoek/OrganisatieLijst.jsx`
- Modify: `frontend/src/views/OnderzoekView.jsx`

**Interfaces:**
- Consumes: `organisatieStatus`, `TOON_STYLE` uit `lib/onderzoekLabels.js` (Task 1); `api.batch(batchId)`, `api.companies(batchId, "")`.
- Produces: `<OrganisatieLijst companies geselecteerdId onSelect />`.
- Produces: `OnderzoekView` levert de driekolomsstructuur; middenpaneel en rechterpaneel zijn in deze taak nog placeholders die in Task 5 en 6 worden ingevuld.

- [ ] **Step 1: Maak de organisatielijst**

Maak `frontend/src/components/onderzoek/OrganisatieLijst.jsx`:

```jsx
import {useMemo, useState} from "react";
import {Search} from "lucide-react";
import {classNames} from "../../lib/format.js";
import {organisatieStatus} from "../../lib/onderzoekLabels.js";

const STATUS_PUNT = {
  neutraal: "bg-slate-300",
  aandacht: "bg-amber-500",
  fout: "bg-red-500",
  gekozen: "bg-emerald-500",
};

export function OrganisatieLijst({companies, geselecteerdId, onSelect}) {
  const [zoek, setZoek] = useState("");
  const [filter, setFilter] = useState("");

  const verrijkt = useMemo(
    () => companies.map((company) => ({...company, status: organisatieStatus(company)})),
    [companies],
  );

  const zichtbaar = useMemo(() => verrijkt.filter((company) => {
    if (filter && company.status.sleutel !== filter) return false;
    const tekst = `${company.naam || ""} ${company.gemeente || ""}`.toLowerCase();
    return tekst.includes(zoek.toLowerCase());
  }), [verrijkt, zoek, filter]);

  const teBeoordelen = verrijkt.filter(
    (company) => company.status.sleutel === "te_beoordelen",
  ).length;
  const gekozen = verrijkt.filter(
    (company) => company.status.sleutel === "gekozen",
  ).length;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="space-y-2 border-b border-line px-3 py-3">
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2.5 top-2.5 text-slate-400"
            size={15}
          />
          <input
            value={zoek}
            onChange={(event) => setZoek(event.target.value)}
            placeholder="Zoek organisatie"
            aria-label="Zoek organisatie"
            className="focus-ring h-9 w-full rounded-md border border-line bg-white pl-8 pr-2 text-sm"
          />
        </div>
        <select
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
          aria-label="Filter op status"
          className="focus-ring h-9 w-full rounded-md border border-line bg-white px-2 text-sm text-slate-600"
        >
          <option value="">Alle statussen</option>
          <option value="te_beoordelen">Te beoordelen</option>
          <option value="gekozen">Bron gekozen</option>
          <option value="niet_gevonden">Geen bron gevonden</option>
          <option value="niet_onderzocht">Nog niet onderzocht</option>
          <option value="mislukt">Mislukt</option>
        </select>
      </div>

      <ul className="min-h-0 flex-1 overflow-y-auto">
        {zichtbaar.map((company) => (
          <li key={company.company_id}>
            <button
              type="button"
              onClick={() => onSelect(company.company_id)}
              aria-current={company.company_id === geselecteerdId ? "true" : undefined}
              className={classNames(
                "focus-ring flex w-full items-start gap-2 border-l-2 px-3 py-2.5 text-left transition",
                company.company_id === geselecteerdId
                  ? "border-l-etil bg-panel"
                  : "border-l-transparent hover:bg-panel",
              )}
            >
              <span
                aria-hidden="true"
                className={classNames(
                  "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
                  STATUS_PUNT[company.status.toon],
                )}
              />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-medium text-ink">
                  {company.naam}
                </span>
                <span className="block truncate text-xs text-slate-500">
                  {company.gemeente} · {company.status.label}
                </span>
              </span>
            </button>
          </li>
        ))}
        {!zichtbaar.length ? (
          <li className="px-3 py-8 text-center text-xs text-slate-500">
            Geen organisaties
          </li>
        ) : null}
      </ul>

      <div className="border-t border-line px-3 py-2 text-xs tabular-nums text-slate-500">
        {teBeoordelen} te beoordelen · {gekozen} klaar
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Bouw de driekolomswerkbank**

Vervang de inhoud van `frontend/src/views/OnderzoekView.jsx` door:

```jsx
import {useEffect, useState} from "react";
import {ChevronLeft} from "lucide-react";
import {Alert} from "../components/Alert.jsx";
import {BatchesView} from "./BatchesView.jsx";
import {OrganisatieLijst} from "../components/onderzoek/OrganisatieLijst.jsx";

export function OnderzoekView({api}) {
  const [batchId, setBatchId] = useState(null);
  const [batch, setBatch] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [geselecteerdId, setGeselecteerdId] = useState(null);
  const [error, setError] = useState("");

  async function load(id) {
    const [batchData, companyData] = await Promise.all([
      api.batch(id),
      api.companies(id, ""),
    ]);
    setBatch(batchData);
    setCompanies(companyData);
    return batchData;
  }

  useEffect(() => {
    if (!batchId) return;
    setGeselecteerdId(null);
    load(batchId).catch((err) => setError(err.message));
  }, [batchId]);

  useEffect(() => {
    if (!batchId || batch?.status !== "running") return undefined;
    const timer = window.setInterval(
      () => load(batchId).catch(() => {}), 5000,
    );
    return () => window.clearInterval(timer);
  }, [batchId, batch?.status]);

  if (!batchId) return <BatchesView api={api} onOpenBatch={setBatchId} />;

  const geselecteerd = companies.find(
    (company) => company.company_id === geselecteerdId,
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-3 border-b border-line px-4 py-2">
        <button
          type="button"
          onClick={() => setBatchId(null)}
          className="focus-ring inline-flex items-center gap-1 rounded-md px-1 py-1 text-sm text-slate-500 transition hover:text-ink"
        >
          <ChevronLeft size={16} />Alle lijsten
        </button>
        <span className="text-sm font-medium text-ink">{batch?.naam}</span>
        <span className="text-xs text-slate-400">{batch?.jaar}</span>
      </div>

      {error ? <div className="px-4 pt-4"><Alert message={error} /></div> : null}

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(220px,1fr)_minmax(0,2fr)] xl:grid-cols-[minmax(240px,1fr)_minmax(0,2fr)_minmax(0,2fr)]">
        <aside className="min-h-0 border-line lg:border-r">
          <OrganisatieLijst
            companies={companies}
            geselecteerdId={geselecteerdId}
            onSelect={setGeselecteerdId}
          />
        </aside>

        <section className="min-h-0 overflow-y-auto border-line xl:border-r">
          {geselecteerd ? (
            <div className="px-5 py-5 text-sm text-slate-500">
              Kandidaten voor {geselecteerd.naam} volgen in de volgende stap.
            </div>
          ) : (
            <div className="px-5 py-16 text-center text-sm text-slate-500">
              Kies een organisatie om de gevonden bronnen te beoordelen.
            </div>
          )}
        </section>

        <section className="hidden min-h-0 overflow-hidden bg-panel xl:block">
          <div className="px-5 py-16 text-center text-sm text-slate-500">
            Bewijs verschijnt hier.
          </div>
        </section>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verifieer build en tests**

Run: `cd frontend && npm run build && npm test`
Expected: build slaagt, tests groen.

- [ ] **Step 4: Visuele controle inclusief responsief gedrag**

Run: `cd frontend && npm run dev`, open een lijst en controleer:
- Bij een breed venster (≥1280px) staan drie kolommen naast elkaar.
- Tussen 1024px en 1280px verdwijnt het bewijspaneel en blijven twee kolommen over.
- Onder 1024px staat alles onder elkaar in één kolom.
- De lijst scrollt zelfstandig; de kop met "Alle lijsten" blijft staan.
- Elke organisatie toont een statuspunt en een leesbaar statuslabel uit het nieuwe vocabulaire.
- Zoeken en filteren werken.

- [ ] **Step 5: Commit**

```bash
cd /Users/arryawillems/Desktop/Projects/KYC4etil
git add frontend/src/components/onderzoek/OrganisatieLijst.jsx frontend/src/views/OnderzoekView.jsx
git commit -m "feat(frontend): drie-panelen werkbank met organisatielijst"
```

---

## Task 5: Kandidatenpaneel en bronkaarten

**Files:**
- Create: `frontend/src/components/onderzoek/BronKaart.jsx`
- Create: `frontend/src/components/onderzoek/KandidatenPaneel.jsx`
- Modify: `frontend/src/views/OnderzoekView.jsx`

**Interfaces:**
- Consumes: `identiteitLabel`, `bereikLabel`, `brontypeLabel`, `bronwaarschuwingen`, `TOON_STYLE` (Task 1); `api.researchCandidates(companyId)`, `api.startResearch(companyId, jaar)`, `api.researchRun(runId)`, `api.reviewResearchCandidate(candidateId, beslissing)`, `api.addManualResearchSource(companyId, body)`.
- Produces: `<BronKaart candidate rang gevraagdJaar isGeselecteerd onBekijk onAccepteer onWijsAf />`.
- Produces: `<KandidatenPaneel api company batchJaar geselecteerdeBronId onSelecteerBron />` — roept `onSelecteerBron(candidate)` aan zodra een bron bekeken wordt.

- [ ] **Step 1: Maak de bronkaart**

Maak `frontend/src/components/onderzoek/BronKaart.jsx`:

```jsx
import {useState} from "react";
import {Check, ChevronDown, ChevronUp, Eye, X} from "lucide-react";
import {classNames} from "../../lib/format.js";
import {
  TOON_STYLE, bereikLabel, bronwaarschuwingen, brontypeLabel, identiteitLabel,
} from "../../lib/onderzoekLabels.js";

function Signaal({label, toon}) {
  return (
    <span className={classNames(
      "inline-flex items-center rounded border px-1.5 py-0.5 text-xs",
      TOON_STYLE[toon],
    )}>
      {label}
    </span>
  );
}

function herkomst(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

export function BronKaart({
  candidate, rang, gevraagdJaar, isGeselecteerd, onBekijk, onAccepteer, onWijsAf,
}) {
  const [toonOnderbouwing, setToonOnderbouwing] = useState(false);
  const identiteit = identiteitLabel(candidate.identity_class);
  const bereik = bereikLabel(candidate.scope_class);
  const waarschuwingen = bronwaarschuwingen({...candidate, gevraagd_jaar: gevraagdJaar});
  const beoordeeld = ["geaccepteerd", "afgewezen"].includes(candidate.status);

  return (
    <article className={classNames(
      "border-l-2 py-5 pl-4 pr-1 transition",
      candidate.status === "geaccepteerd"
        ? "border-l-emerald-500"
        : isGeselecteerd ? "border-l-etil" : "border-l-transparent",
      candidate.status === "afgewezen" && "opacity-50",
    )}>
      <div className="flex items-baseline gap-2">
        <span className="text-xs tabular-nums text-slate-400">{rang}</span>
        <span className="text-sm font-medium text-ink">
          {brontypeLabel(candidate.brontype)}
        </span>
        <span className="truncate text-xs text-slate-400">
          {herkomst(candidate.url)}
        </span>
        {candidate.status === "geaccepteerd" ? (
          <span className="ml-auto inline-flex items-center gap-1 rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-xs text-emerald-900">
            <Check size={11} />Gekozen
          </span>
        ) : null}
      </div>

      {candidate.bewijsfragment ? (
        <blockquote className="mt-3 text-base leading-relaxed text-ink">
          “{candidate.bewijsfragment}”
        </blockquote>
      ) : (
        <p className="mt-3 text-sm italic text-slate-500">
          Geen citaat geëxtraheerd — beoordeel de bron zelf.
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <Signaal {...identiteit} />
        <Signaal {...bereik} />
        {candidate.wp_gevonden != null ? (
          <span className="text-xs tabular-nums text-slate-600">
            {candidate.wp_gevonden} {candidate.eenheid === "fte" ? "FTE" : "WP"}
          </span>
        ) : null}
        {candidate.verslagjaar ? (
          <span className="text-xs text-slate-500">
            verslagjaar {candidate.verslagjaar}
          </span>
        ) : null}
      </div>

      {waarschuwingen.length ? (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {waarschuwingen.map((item) => (
            <Signaal key={item.label} {...item} />
          ))}
        </div>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => onBekijk(candidate)}
          className="focus-ring inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-sm text-ink transition hover:bg-panel"
        >
          <Eye size={14} />Bewijs bekijken
        </button>
        {!beoordeeld ? (
          <>
            <button
              type="button"
              onClick={() => onAccepteer(candidate)}
              className="focus-ring inline-flex items-center gap-1.5 rounded-md bg-ink px-2.5 py-1.5 text-sm text-white transition hover:opacity-90"
            >
              <Check size={14} />Accepteren
            </button>
            <button
              type="button"
              onClick={() => onWijsAf(candidate)}
              className="focus-ring inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-slate-500 transition hover:text-ink"
            >
              <X size={14} />Afwijzen
            </button>
          </>
        ) : null}
        <button
          type="button"
          onClick={() => setToonOnderbouwing((open) => !open)}
          aria-expanded={toonOnderbouwing}
          className="focus-ring ml-auto inline-flex items-center gap-1 rounded px-1 py-1 text-xs text-slate-400 transition hover:text-slate-600"
        >
          Onderbouwing
          {toonOnderbouwing ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
        </button>
      </div>

      {toonOnderbouwing ? (
        <dl className="mt-3 space-y-1 border-t border-line pt-3 text-xs text-slate-500">
          {candidate.validaties?.intelligente_review?.reden ? (
            <div>
              <dt className="inline font-medium text-slate-600">Bronreview: </dt>
              <dd className="inline">{candidate.validaties.intelligente_review.reden}</dd>
            </div>
          ) : null}
          {candidate.publicatiedatum ? (
            <div>
              <dt className="inline font-medium text-slate-600">Gepubliceerd: </dt>
              <dd className="inline">{candidate.publicatiedatum}</dd>
            </div>
          ) : null}
          {candidate.informatie_peilmoment ? (
            <div>
              <dt className="inline font-medium text-slate-600">Peilmoment: </dt>
              <dd className="inline">{candidate.informatie_peilmoment}</dd>
            </div>
          ) : null}
          <div>
            <dt className="inline font-medium text-slate-600">Bron-URL: </dt>
            <dd className="inline break-all">{candidate.url}</dd>
          </div>
        </dl>
      ) : null}
    </article>
  );
}
```

- [ ] **Step 2: Maak het kandidatenpaneel**

Maak `frontend/src/components/onderzoek/KandidatenPaneel.jsx`:

```jsx
import {useEffect, useState} from "react";
import {Plus, RefreshCw, Search} from "lucide-react";
import {Alert} from "../Alert.jsx";
import {BronKaart} from "./BronKaart.jsx";

export function KandidatenPaneel({
  api, company, batchJaar, geselecteerdeBronId, onSelecteerBron,
}) {
  const [items, setItems] = useState([]);
  const [diagnostiek, setDiagnostiek] = useState({});
  const [run, setRun] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [handmatigOpen, setHandmatigOpen] = useState(false);
  const [handmatigUrl, setHandmatigUrl] = useState("");

  const gevraagdJaar = batchJaar ? batchJaar - 1 : null;

  async function laadKandidaten() {
    const data = await api.researchCandidates(company.company_id);
    setItems(data.items || []);
    setDiagnostiek(data.diagnostiek || {});
  }

  useEffect(() => {
    setRun(null);
    setError("");
    laadKandidaten().catch((err) => setError(err.message));
  }, [company.company_id]);

  useEffect(() => {
    if (!run?.id || !["pending", "running"].includes(run.status)) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const volgende = await api.researchRun(run.id);
        setRun(volgende);
        if (["completed", "error"].includes(volgende.status)) {
          setItems(volgende.kandidaten || []);
          setDiagnostiek(volgende.diagnostiek || {});
        }
      } catch (err) {
        setError(err.message);
      }
    }, 2000);
    return () => window.clearInterval(timer);
  }, [run?.id, run?.status]);

  const loopt = run && ["pending", "running"].includes(run.status);

  async function startOnderzoek() {
    setBusy(true);
    setError("");
    try {
      const gestart = await api.startResearch(company.company_id, gevraagdJaar);
      setRun({id: gestart.run_id, status: gestart.status});
      setItems([]);
      setDiagnostiek({});
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function beoordeel(candidate, beslissing) {
    setError("");
    try {
      await api.reviewResearchCandidate(candidate.id, beslissing);
      await laadKandidaten();
    } catch (err) {
      setError(err.message);
    }
  }

  async function voegHandmatigToe(event) {
    event.preventDefault();
    setError("");
    try {
      await api.addManualResearchSource(company.company_id, {url: handmatigUrl});
      setHandmatigUrl("");
      setHandmatigOpen(false);
      await laadKandidaten();
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="px-5 py-5">
      <header className="mb-5">
        <h2 className="text-lg font-semibold text-ink">{company.naam}</h2>
        <p className="mt-0.5 text-xs text-slate-500">
          {[company.gemeente, company.vestigingsnummer, company.kvk_nummer
            ? `KvK ${company.kvk_nummer}` : null]
            .filter(Boolean).join(" · ")}
        </p>
      </header>

      {error ? <Alert message={error} /> : null}

      {items.length ? (
        <div className="divide-y divide-line border-y border-line">
          {items.map((candidate, index) => (
            <BronKaart
              key={candidate.id}
              candidate={candidate}
              rang={candidate.rang || index + 1}
              gevraagdJaar={gevraagdJaar}
              isGeselecteerd={candidate.id === geselecteerdeBronId}
              onBekijk={onSelecteerBron}
              onAccepteer={(item) => beoordeel(item, "accepteren")}
              onWijsAf={(item) => beoordeel(item, "afwijzen")}
            />
          ))}
        </div>
      ) : loopt ? (
        <p className="py-10 text-center text-sm text-slate-500">
          De agent onderzoekt websites, documenten en recente media…
        </p>
      ) : (
        <p className="py-10 text-center text-sm text-slate-500">
          Nog geen bronnen. Start een onderzoek of voeg zelf een bron toe.
        </p>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={startOnderzoek}
          disabled={busy || loopt}
          className="focus-ring inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-sm text-ink transition hover:bg-panel disabled:opacity-50"
        >
          {loopt ? <RefreshCw size={14} /> : <Search size={14} />}
          {loopt ? "Onderzoek loopt…" : items.length ? "Opnieuw zoeken" : "Bronnen zoeken"}
        </button>
        <button
          type="button"
          onClick={() => setHandmatigOpen((open) => !open)}
          className="focus-ring inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-sm text-slate-500 transition hover:text-ink"
        >
          <Plus size={14} />Bron toevoegen
        </button>
      </div>

      {handmatigOpen ? (
        <form onSubmit={voegHandmatigToe} className="mt-3 flex gap-2">
          <input
            type="url"
            required
            value={handmatigUrl}
            onChange={(event) => setHandmatigUrl(event.target.value)}
            placeholder="https://organisatie.nl/over-ons"
            aria-label="Bron-URL"
            className="focus-ring h-9 flex-1 rounded-md border border-line px-2 text-sm"
          />
          <button
            type="submit"
            className="focus-ring rounded-md bg-ink px-3 text-sm text-white transition hover:opacity-90"
          >
            Toevoegen
          </button>
        </form>
      ) : null}

      {run?.status === "error" ? (
        <p className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          Het onderzoek is mislukt: {run.fout || "onbekende fout"}
        </p>
      ) : null}
    </div>
  );
}
```

Let op: `diagnostiek` wordt hier al opgehaald en in state gehouden, maar nog niet getoond. Task 7 voegt de weergave toe.

- [ ] **Step 3: Sluit het paneel aan in de werkbank**

In `frontend/src/views/OnderzoekView.jsx`, voeg de import toe:

```jsx
import {KandidatenPaneel} from "../components/onderzoek/KandidatenPaneel.jsx";
```

Voeg een state voor de geselecteerde bron toe, direct na `const [geselecteerdId, setGeselecteerdId] = useState(null);`:

```jsx
  const [geselecteerdeBron, setGeselecteerdeBron] = useState(null);
```

Een wisseling van organisatie óf van lijst moet de bronselectie leegmaken,
anders blijft het bewijspaneel een bron van de vorige organisatie tonen.

Vervang daarvoor in de bestaande `useEffect` op `[batchId]` het blok:

```jsx
  useEffect(() => {
    if (!batchId) return;
    setGeselecteerdId(null);
    load(batchId).catch((err) => setError(err.message));
  }, [batchId]);
```

door:

```jsx
  useEffect(() => {
    if (!batchId) return;
    setGeselecteerdId(null);
    setGeselecteerdeBron(null);
    load(batchId).catch((err) => setError(err.message));
  }, [batchId]);
```

En vervang de `onSelect`-prop van `OrganisatieLijst`:

```jsx
            onSelect={setGeselecteerdId}
```

door:

```jsx
            onSelect={(id) => {
              setGeselecteerdId(id);
              setGeselecteerdeBron(null);
            }}
```

Vervang vervolgens het middenpaneel:

```jsx
        <section className="min-h-0 overflow-y-auto border-line xl:border-r">
          {geselecteerd ? (
            <div className="px-5 py-5 text-sm text-slate-500">
              Kandidaten voor {geselecteerd.naam} volgen in de volgende stap.
            </div>
          ) : (
```

door:

```jsx
        <section className="min-h-0 overflow-y-auto border-line xl:border-r">
          {geselecteerd ? (
            <KandidatenPaneel
              key={geselecteerd.company_id}
              api={api}
              company={geselecteerd}
              batchJaar={batch?.jaar}
              geselecteerdeBronId={geselecteerdeBron?.id}
              onSelecteerBron={setGeselecteerdeBron}
            />
          ) : (
```

- [ ] **Step 4: Verifieer build en tests**

Run: `cd frontend && npm run build && npm test`
Expected: build slaagt, tests groen.

- [ ] **Step 5: Visuele controle**

Run: `cd frontend && npm run dev`, open een lijst met eerder uitgevoerd onderzoek en controleer:
- Het citaat is het grootste, best leesbare element van elke kaart.
- Elke kaart toont twee signalen (identiteit en bereik) in leesbaar Nederlands.
- Er is nergens een percentage of een rauwe enum zichtbaar.
- Waarschuwingen verschijnen alleen wanneer ze gelden; een schone bron heeft géén groene badge.
- "Onderbouwing" klapt de technische details open.
- Accepteren markeert de kaart en toont "Gekozen"; afwijzen dimt de kaart.
- "Bronnen zoeken" start een onderzoek en het paneel ververst zichzelf.

- [ ] **Step 6: Commit**

```bash
cd /Users/arryawillems/Desktop/Projects/KYC4etil
git add frontend/src/components/onderzoek/BronKaart.jsx frontend/src/components/onderzoek/KandidatenPaneel.jsx frontend/src/views/OnderzoekView.jsx
git commit -m "feat(frontend): bronkaarten met citaat centraal en tweeassig vocabulaire"
```

---

## Task 6: Bewijspaneel

**Files:**
- Create: `frontend/src/components/onderzoek/BewijsPaneel.jsx`
- Modify: `frontend/src/views/OnderzoekView.jsx`

**Interfaces:**
- Consumes: `bewijsUrl` uit `lib/evidenceLink.js` (Task 1); `brontypeLabel` uit `lib/onderzoekLabels.js`.
- Produces: `<BewijsPaneel candidate />`.

- [ ] **Step 1: Maak het bewijspaneel**

Maak `frontend/src/components/onderzoek/BewijsPaneel.jsx`:

```jsx
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
```

- [ ] **Step 2: Sluit het bewijspaneel aan**

In `frontend/src/views/OnderzoekView.jsx`, voeg de import toe:

```jsx
import {BewijsPaneel} from "../components/onderzoek/BewijsPaneel.jsx";
```

Vervang het placeholder-rechterpaneel:

```jsx
        <section className="hidden min-h-0 overflow-hidden bg-panel xl:block">
          <div className="px-5 py-16 text-center text-sm text-slate-500">
            Bewijs verschijnt hier.
          </div>
        </section>
```

door:

```jsx
        <section className="hidden min-h-0 overflow-hidden bg-panel xl:block">
          <BewijsPaneel candidate={geselecteerdeBron} />
        </section>
```

Onder 1280px bestaat het derde paneel niet. Zorg dat de gebruiker het bewijs daar alsnog bereikt: voeg direct ná die `<section>` een variant toe die alleen op smallere schermen verschijnt en het bewijs onder de kandidaten toont:

```jsx
        {geselecteerdeBron ? (
          <section className="min-h-[24rem] border-t border-line bg-panel xl:hidden">
            <BewijsPaneel candidate={geselecteerdeBron} />
          </section>
        ) : null}
```

- [ ] **Step 3: Verifieer build en tests**

Run: `cd frontend && npm run build && npm test`
Expected: build slaagt, tests groen.

- [ ] **Step 4: Visuele controle van beide bewijspaden**

Run: `cd frontend && npm run dev` en controleer met een organisatie die zowel een PDF- als een HTML-bron heeft:
- **PDF:** "Bewijs bekijken" toont het document ingesloten in het rechterpaneel, geopend op de juiste pagina, met het citaat gemarkeerd.
- **HTML:** het rechterpaneel toont de passage groot, plus de knop "Open bron op de bewijsplek". Die knop opent een nieuw tabblad; controleer dat de browser naar de passage scrollt en die markeert.
- Onder 1280px verschijnt het bewijs onder de kandidatenlijst in plaats van ernaast.
- Een andere bron kiezen ververst het paneel.

- [ ] **Step 5: Commit**

```bash
cd /Users/arryawillems/Desktop/Projects/KYC4etil
git add frontend/src/components/onderzoek/BewijsPaneel.jsx frontend/src/views/OnderzoekView.jsx
git commit -m "feat(frontend): bewijspaneel met ingesloten pdf en tekstfragment voor webpagina's"
```

---

## Task 7: Diagnostiek bij niets gevonden

**Files:**
- Create: `frontend/src/components/onderzoek/Diagnostiek.jsx`
- Modify: `frontend/src/components/onderzoek/KandidatenPaneel.jsx`

**Interfaces:**
- Consumes: het `diagnostiek`-object dat `api.researchCandidates` en `api.researchRun` teruggeven.
- Produces: `<Diagnostiek diagnostiek />`.

- [ ] **Step 1: Maak de diagnostiekweergave**

Maak `frontend/src/components/onderzoek/Diagnostiek.jsx`:

```jsx
export function Diagnostiek({diagnostiek}) {
  if (!diagnostiek || !Object.keys(diagnostiek).length) return null;

  const website = diagnostiek.website_resolution;
  const redenen = Object.entries(diagnostiek.afwijsredenen || {});

  return (
    <section className="rounded-md border border-line bg-panel p-4">
      <h3 className="text-sm font-medium text-ink">
        Geen bruikbare bron gevonden
      </h3>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">
        De agent vond {diagnostiek.zoekresultaten || 0} zoekresultaten,
        onderzocht {diagnostiek.onderzochte_paginas || 0} pagina’s en las{" "}
        {diagnostiek.gelezen_documenten || 0} documenten. Daarvan vielen er{" "}
        {diagnostiek.afgewezen_documenten || 0} af bij de kwaliteitscontrole.
      </p>

      <p className="mt-3 text-xs text-slate-500">
        Officiële website:{" "}
        {website?.website_url ? (
          <a
            href={website.website_url}
            target="_blank"
            rel="noreferrer"
            className="focus-ring text-ink underline"
          >
            {website.website_url}
          </a>
        ) : (
          "niet gevonden"
        )}
      </p>

      {redenen.length ? (
        <p className="mt-1 text-xs text-slate-500">
          Redenen:{" "}
          {redenen
            .map(([reden, aantal]) => `${reden.replaceAll("_", " ")} (${aantal})`)
            .join(", ")}
        </p>
      ) : null}

      {diagnostiek.afwijzingen?.length ? (
        <details className="mt-3">
          <summary className="focus-ring cursor-pointer text-xs text-slate-500 hover:text-ink">
            Bekijk de {diagnostiek.afwijzingen.length} afgewezen bronnen
          </summary>
          <ul className="mt-2 space-y-1.5">
            {diagnostiek.afwijzingen.map((item) => (
              <li key={item.url} className="text-xs leading-relaxed">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="focus-ring text-ink underline"
                >
                  {item.titel || item.url}
                </a>
                <span className="text-slate-500">
                  {" — "}
                  {item.review_reden
                    || item.redenen?.join(", ").replaceAll("_", " ")
                    || "afgewezen"}
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </section>
  );
}
```

- [ ] **Step 2: Toon diagnostiek uitsluitend wanneer er niets gevonden is**

In `frontend/src/components/onderzoek/KandidatenPaneel.jsx`, voeg de import toe:

```jsx
import {Diagnostiek} from "./Diagnostiek.jsx";
```

Vervang de lege-toestand-tak:

```jsx
      ) : (
        <p className="py-10 text-center text-sm text-slate-500">
          Nog geen bronnen. Start een onderzoek of voeg zelf een bron toe.
        </p>
      )}
```

door:

```jsx
      ) : Object.keys(diagnostiek).length ? (
        <Diagnostiek diagnostiek={diagnostiek} />
      ) : (
        <p className="py-10 text-center text-sm text-slate-500">
          Nog geen bronnen. Start een onderzoek of voeg zelf een bron toe.
        </p>
      )}
```

Hiermee verschijnt diagnostiek alleen wanneer een run wél gedraaid heeft maar geen kandidaat opleverde — precies de situatie waarin de onderzoeker wil weten waarom.

- [ ] **Step 3: Verifieer build en tests**

Run: `cd frontend && npm run build && npm test`
Expected: build slaagt, tests groen.

- [ ] **Step 4: Visuele controle**

Run: `cd frontend && npm run dev` en controleer met een organisatie met status "Geen bron gevonden":
- Het middenpaneel legt in gewone taal uit hoeveel resultaten en documenten er waren en waarom ze afvielen.
- De afgewezen bronnen zijn uitklapbaar met hun reden.
- Bij een organisatie mét kandidaten is er géén diagnostiekblok zichtbaar.

- [ ] **Step 5: Commit**

```bash
cd /Users/arryawillems/Desktop/Projects/KYC4etil
git add frontend/src/components/onderzoek/Diagnostiek.jsx frontend/src/components/onderzoek/KandidatenPaneel.jsx
git commit -m "feat(frontend): diagnostiek tonen wanneer de agent niets bruikbaars vond"
```

---

## Task 8: Jaarverslagenmonitoring in dezelfde vormgeving

**Files:**
- Modify: `frontend/src/views/MonitoringView.jsx`

**Interfaces:**
- Consumes: `organisatieStatus` niet (monitoring heeft eigen statussen); wel `KandidatenPaneel`, `BewijsPaneel`, `OrganisatieLijst` uit Tasks 4-6; `api.monitoringStatus()`, `api.monitorRun()`.

- [ ] **Step 1: Herbouw MonitoringView als werkbank**

Vervang de volledige inhoud van `frontend/src/views/MonitoringView.jsx` door:

```jsx
import {useEffect, useMemo, useState} from "react";
import {RefreshCw} from "lucide-react";
import {Alert} from "../components/Alert.jsx";
import {IconButton} from "../components/IconButton.jsx";
import {OrganisatieLijst} from "../components/onderzoek/OrganisatieLijst.jsx";
import {KandidatenPaneel} from "../components/onderzoek/KandidatenPaneel.jsx";
import {BewijsPaneel} from "../components/onderzoek/BewijsPaneel.jsx";

/**
 * De monitoringlijst levert een eigen statusvorm. Vertaal die naar dezelfde
 * vorm als de onderzoeksmodule verwacht, zodat OrganisatieLijst herbruikbaar
 * blijft en er precies één manier is om een bron te beoordelen.
 */
function alsOnderzoeksCompany(company) {
  if (company.fout) return {...company, research_status: "error"};
  if (company.nieuwe_bevinding) {
    return {
      ...company,
      research_status: "completed",
      research_resultaat_status: "review_nodig",
    };
  }
  if (!company.laatste_bron_url) {
    return {
      ...company,
      research_status: "completed",
      research_resultaat_status: "niet_gevonden",
    };
  }
  return {
    ...company,
    research_status: "completed",
    research_review_status: "geaccepteerd",
  };
}

export function MonitoringView({api}) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [geselecteerdId, setGeselecteerdId] = useState(null);
  const [geselecteerdeBron, setGeselecteerdeBron] = useState(null);

  async function load() {
    setStatus(await api.monitoringStatus());
  }

  useEffect(() => {
    load().catch((err) => setError(err.message));
    const timer = window.setInterval(() => load().catch(() => {}), 10000);
    return () => window.clearInterval(timer);
  }, []);

  async function nuControleren() {
    setBusy(true);
    setError("");
    try {
      await api.monitorRun();
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const batch = status?.batch;
  const companies = useMemo(
    () => (status?.companies || []).map(alsOnderzoeksCompany),
    [status],
  );
  const geselecteerd = companies.find(
    (company) => company.company_id === geselecteerdId,
  );

  if (!batch) {
    return (
      <div className="px-6 py-16 text-center text-sm text-slate-500">
        {error
          ? error
          : "Nog geen monitoringlijst ingesteld."}
      </div>
    );
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-3 border-b border-line px-4 py-2">
        <span className="text-sm font-medium text-ink">{batch.naam}</span>
        <span className="text-xs text-slate-400">
          {status.gecontroleerd} van {status.totaal} gecontroleerd
        </span>
        <IconButton
          icon={RefreshCw}
          variant="quiet"
          onClick={nuControleren}
          disabled={busy}
          className="ml-auto"
        >
          {busy ? "Bezig…" : "Nu controleren"}
        </IconButton>
      </div>

      {error ? <div className="px-4 pt-4"><Alert message={error} /></div> : null}

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(220px,1fr)_minmax(0,2fr)] xl:grid-cols-[minmax(240px,1fr)_minmax(0,2fr)_minmax(0,2fr)]">
        <aside className="min-h-0 border-line lg:border-r">
          <OrganisatieLijst
            companies={companies}
            geselecteerdId={geselecteerdId}
            onSelect={(id) => {
              setGeselecteerdId(id);
              setGeselecteerdeBron(null);
            }}
          />
        </aside>

        <section className="min-h-0 overflow-y-auto border-line xl:border-r">
          {geselecteerd ? (
            <KandidatenPaneel
              key={geselecteerd.company_id}
              api={api}
              company={geselecteerd}
              batchJaar={batch.jaar}
              geselecteerdeBronId={geselecteerdeBron?.id}
              onSelecteerBron={setGeselecteerdeBron}
            />
          ) : (
            <div className="px-5 py-16 text-center text-sm text-slate-500">
              Kies een organisatie om de gevonden bronnen te beoordelen.
            </div>
          )}
        </section>

        <section className="hidden min-h-0 overflow-hidden bg-panel xl:block">
          <BewijsPaneel candidate={geselecteerdeBron} />
        </section>

        {geselecteerdeBron ? (
          <section className="min-h-[24rem] border-t border-line bg-panel xl:hidden">
            <BewijsPaneel candidate={geselecteerdeBron} />
          </section>
        ) : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verifieer build en tests**

Run: `cd frontend && npm run build && npm test`
Expected: build slaagt, tests groen.

- [ ] **Step 3: Controleer dat er geen verweesde imports resteren**

Run: `cd frontend && grep -rn "from \"../components/Shell.jsx\"\|LabelBadge\|zekerheid.js\|lib/constants.js" src/App.jsx src/views/OnderzoekView.jsx src/views/BatchesView.jsx src/views/MonitoringView.jsx src/components/onderzoek/`
Expected: geen resultaten — de nieuwe schermen gebruiken geen legacy-componenten meer. (De legacy-viewbestanden zelf blijven bestaan en mogen deze imports houden.)

- [ ] **Step 4: Visuele eindcontrole van beide modules**

Run: `cd frontend && npm run dev` en controleer:
- Beide modules delen dezelfde werkbank en hetzelfde vocabulaire.
- In monitoring werkt "Nu controleren" en ververst het overzicht.
- Een organisatie beoordelen werkt in beide modules identiek, inclusief bewijs.
- Nergens in de applicatie is nog een legacy-scherm of legacy-label bereikbaar.

- [ ] **Step 5: Commit**

```bash
cd /Users/arryawillems/Desktop/Projects/KYC4etil
git add frontend/src/views/MonitoringView.jsx
git commit -m "feat(frontend): monitoring gebruikt dezelfde werkbank en vormgeving als onderzoek"
```

---

## Na afloop

Alle punten uit
[2026-07-26-onderzoekswerkbank-frontend-design.md](../specs/2026-07-26-onderzoekswerkbank-frontend-design.md)
zijn hiermee geïmplementeerd. De succescriteria uit §11 van dat document zijn
de acceptatietest.

Bewust niet gedaan, conform §10 van het design: toetsenbordnavigatie,
deeplinks per organisatie, en het verwijderen van backend-endpoints die door
het verbergen van views ongebruikt raken.
