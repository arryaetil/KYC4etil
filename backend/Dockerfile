# De werkbank als één image: Linux, Python, Chromium en de code.
#
# Waarom dit bestand bestaat: Chromium draait op Railway alleen dankzij een
# omgevingsvariabele RAILPACK_DEPLOY_APT_PACKAGES met twintig X11-bibliotheken.
# Die staat in een instellingenscherm en in geen enkel bestand — raakt hij weg,
# dan is er niets om op terug te vallen. Hier staat het in de repository, en
# draait het overal hetzelfde: Railway, Azure, of een laptop.
#
# Bouwen en draaien (vanuit backend/):
#   docker build -t kyc4etil .
#   docker run --rm -p 8000:8080 --env-file .env kyc4etil

# ---------------------------------------------------------------------------
# 1. Bouwen — hier staan de compilers die sommige pakketten nodig hebben
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS bouwer

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Niet elk pakket levert een kant-en-klare wheel voor deze combinatie van
# Python en architectuur; dan wordt er ter plekke gecompileerd. gcc hoort in
# deze laag en niet in de laag die straks draait.
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Alleen requirements.txt kopiëren, nog niet de code. Zolang dit bestand niet
# verandert hergebruikt Docker deze laag, en dat scheelt bij elke build minuten.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# 2. Draaien — alleen wat nodig is om te werken
# ---------------------------------------------------------------------------
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    # 0 betekent: bewaar de browsers in de playwright-map zelf, dus binnen de
    # virtualenv en daarmee binnen deze image. Zonder dit landen ze in de
    # thuismap van de gebruiker en zijn ze bij een herstart weg.
    PLAYWRIGHT_BROWSERS_PATH=0

COPY --from=bouwer /opt/venv /opt/venv

WORKDIR /app

# Chromium plus de systeembibliotheken eromheen. `--with-deps` laat Playwright
# zelf bepalen welke apt-pakketten zijn versie nodig heeft; dat is precies de
# lijst die nu handmatig in een Railway-variabele staat. crawl4ai-setup zet
# daarna zijn eigen configuratie klaar.
RUN playwright install --with-deps chromium \
 && crawl4ai-setup \
 && rm -rf /var/lib/apt/lists/*

# Bewijzen dat de browser ook echt start, hier in de build en niet pas tijdens
# een onderzoek. Een ontbrekende systeembibliotheek geeft geen foutmelding bij
# het installeren — die merk je pas als crawl4ai een pagina probeert te openen,
# en dan komt het aan als "niets gevonden". Faalt dit, dan faalt de build, en
# een mislukte build vervangt niets wat het wel deed.
RUN python -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage']); print('chromium start op:', b.version); b.close(); p.stop()"  && python -c "import crawl4ai; print('crawl4ai', crawl4ai.__version__)"

# Pas hier de code. Alles hierboven verandert zelden, dit bij elke commit —
# staat het bovenaan, dan wordt Chromium bij elke tekstwijziging opnieuw
# geïnstalleerd.
COPY . .

# Documenten en back-ups staan buiten de image, op een gemount volume. Blijft
# dat leeg, dan schrijft de applicatie niets weg in plaats van naar een schijf
# die bij de volgende deploy verdwijnt (zie app/documenten.py).
ENV BRONDOCUMENTEN_PAD=/data/brondocumenten \
    BACKUP_PAD=/data/brondocumenten/_backups
VOLUME ["/data/brondocumenten"]

# 8080 is wat Azure App Service standaard verwacht. Railway en Container Apps
# geven een eigen poort mee via $PORT; die wint.
ENV PORT=8080
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT','8080') + '/health').read()"

# Shell-vorm, zodat ${PORT} op het moment van starten wordt ingevuld en niet
# als letterlijke tekst wordt doorgegeven.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}
