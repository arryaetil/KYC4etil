"""Vul ontbrekende jaarverslag-baseline-URL's zonder LLM/API-key.

Dit script gebruikt publieke Brave Search-resultaten en een conservatieve
score op URL/titel. Het schrijft alleen bij voldoende confidence naar het vaste
CSV-bestand; twijfelgevallen blijven leeg en komen in een rapport.

Gebruik vanuit repo-root:
    python3 backend/scripts/backfill_monitoring_urls_no_llm.py --limit 20
    python3 backend/scripts/backfill_monitoring_urls_no_llm.py --apply
"""
from __future__ import annotations

import argparse
import base64
import csv
import html
import re
import ssl
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


CSV_PAD = Path(__file__).resolve().parents[1] / "data" / "jaarverslag_monitoringlijst.csv"
RAPPORT_PAD = Path("/tmp/monitoring_url_backfill_report.csv")

POSITIEVE_TERMEN = (
    "jaarverslag", "jaarrekening", "bestuursverslag", "jaarstukken",
    "annual report", "annual-report", "annual_report", "integrated report",
    "integrated-report", "csr report", "csr_report", "sociaal jaarverslag",
    "maatschappelijk verslag", "publicaties jaarverslag",
)
NEGATIEVE_TERMEN = (
    "jaarplan", "begroting", "budget", "poster", "proxy-statement", "proxy statement",
    "vacature", "werken-bij", "contact", "privacy", "cookie", "linkedin",
    "facebook", "youtube", "wikipedia", "creditsafe", "adoc.pub", "issuu",
    "commissiemer", "kvk", "drimble", "company.info", "openingstijden",
    "cao-", "cao_", "arbeidsvoorwaarden", "college van beroep", "clientenraad",
    "cliëntenraad", "medezeggenschap", "jaarplan_clientenraad", "jaarverslag_raad",
)


@dataclass
class Kandidaat:
    naam: str
    url: str
    titel: str
    score: int
    query: str
    reden: str


def _tekst(waarde: str | None) -> str:
    return (waarde or "").strip()


def _clean_html(waarde: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<.*?>", " ", html.unescape(waarde))).strip()


def _decode_bing_url(url: str) -> str:
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    waarde = qs.get("u", [""])[0]
    if not waarde.startswith("a1"):
        return url
    payload = waarde[2:]
    payload += "=" * ((4 - len(payload) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(payload).decode("utf-8")
    except Exception:
        return url


def _search_brave(query: str, timeout: int = 20) -> list[tuple[str, str]]:
    params = urllib.parse.urlencode({"q": query, "source": "web"})
    request = urllib.request.Request(
        f"https://search.brave.com/search?{params}",
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.6",
        },
    )
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        body = response.read().decode("utf-8", "ignore")

    resultaten: list[tuple[str, str]] = []
    gezien: set[str] = set()
    for url, titel_html in re.findall(r'<a[^>]+href="(https?://[^"]+)"[^>]*>(.*?)</a>', body, re.S):
        url = html.unescape(url)
        titel = _clean_html(titel_html)
        if not titel or "search.brave.com" in url:
            continue
        if url in gezien:
            continue
        gezien.add(url)
        resultaten.append((titel, url))
        if len(resultaten) >= 12:
            break
    return resultaten


def _zoek_queries(naam: str) -> list[str]:
    basis = naam.replace(" - Filiaal", "").strip()
    return [
        f'"{basis}" jaarverslag 2025 pdf',
        f'"{basis}" jaarverslag 2024 pdf',
        f'"{basis}" bestuursverslag jaarrekening pdf',
        f'"{basis}" "annual report" pdf',
    ]


def _score(naam: str, titel: str, url: str) -> tuple[int, str]:
    haystack = f"{titel} {urllib.parse.unquote(url)}".casefold()
    score = 0
    redenen: list[str] = []

    naam_tokens = [t for t in re.split(r"[^a-z0-9]+", naam.casefold()) if len(t) >= 4]
    token_hits = sum(1 for token in naam_tokens[:4] if token in haystack)
    score += min(token_hits * 6, 18)
    if token_hits:
        redenen.append(f"naam_tokens={token_hits}")

    for term in POSITIEVE_TERMEN:
        if term in haystack:
            score += 18
            redenen.append(term)
            break

    if ".pdf" in haystack or " pdf" in haystack:
        score += 8
        redenen.append("pdf")

    for jaar, punten in (("2025", 18), ("2024", 14), ("2023", 6), ("2026", 3)):
        if jaar in haystack:
            score += punten
            redenen.append(jaar)
            break

    for term in NEGATIEVE_TERMEN:
        if term in haystack:
            score -= 30
            redenen.append(f"-{term}")
            break

    if "://" in url and any(host in urllib.parse.urlparse(url).netloc for host in ("rijksoverheid.nl", "jaarverslagenzorg.nl")):
        score += 5
        redenen.append("vertrouwde_publicatiehost")

    parsed = urllib.parse.urlparse(url)
    if parsed.netloc.endswith(".nl") or parsed.netloc.endswith(".org") or parsed.netloc.endswith(".com"):
        score += 2

    return score, ";".join(redenen)


def _beste_kandidaat(naam: str, pauze: float) -> Kandidaat | None:
    beste: Kandidaat | None = None
    for query in _zoek_queries(naam):
        try:
            resultaten = _search_brave(query)
        except Exception as exc:
            print(f"zoekfout\t{naam}\t{type(exc).__name__}: {exc}")
            resultaten = []
        for titel, url in resultaten:
            url = _decode_bing_url(url)
            score, reden = _score(naam, titel, url)
            kandidaat = Kandidaat(naam=naam, url=url, titel=titel, score=score, query=query, reden=reden)
            if beste is None or kandidaat.score > beste.score:
                beste = kandidaat
        time.sleep(pauze)
        if beste and beste.score >= 48:
            break
    return beste


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(CSV_PAD))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--threshold", type=int, default=62)
    parser.add_argument("--sleep", type=float, default=2.0)
    args = parser.parse_args()

    csv_pad = Path(args.csv)
    rows = list(csv.DictReader(csv_pad.open(newline="", encoding="utf-8-sig")))
    ontbrekend = [rij for rij in rows if not _tekst(rij.get("jaarverslag_url"))]
    if args.limit:
        ontbrekend = ontbrekend[:args.limit]

    rapport: list[dict[str, str | int]] = []
    updates: dict[str, str] = {}
    for index, rij in enumerate(ontbrekend, 1):
        naam = _tekst(rij.get("naam"))
        kandidaat = _beste_kandidaat(naam, args.sleep)
        if kandidaat:
            status = "accepted" if kandidaat.score >= args.threshold else "rejected"
            if status == "accepted":
                updates[naam.casefold()] = kandidaat.url
            rapport.append({
                "status": status,
                "naam": naam,
                "score": kandidaat.score,
                "url": kandidaat.url,
                "titel": kandidaat.titel,
                "query": kandidaat.query,
                "reden": kandidaat.reden,
            })
            print(f"{index}/{len(ontbrekend)}\t{status}\t{kandidaat.score}\t{naam}\t{kandidaat.url}")
        else:
            rapport.append({"status": "missing", "naam": naam, "score": 0, "url": "", "titel": "", "query": "", "reden": ""})
            print(f"{index}/{len(ontbrekend)}\tmissing\t0\t{naam}")

    with RAPPORT_PAD.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["status", "naam", "score", "url", "titel", "query", "reden"])
        writer.writeheader()
        writer.writerows(rapport)

    if args.apply and updates:
        for rij in rows:
            naam = _tekst(rij.get("naam")).casefold()
            if not _tekst(rij.get("jaarverslag_url")) and naam in updates:
                rij["jaarverslag_url"] = updates[naam]
        with csv_pad.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["naam", "cb_er", "jaarverslag_url"])
            writer.writeheader()
            writer.writerows(rows)

    print(f"rapport={RAPPORT_PAD}")
    print(f"accepted={sum(1 for r in rapport if r['status'] == 'accepted')}")
    print(f"rejected={sum(1 for r in rapport if r['status'] == 'rejected')}")
    print(f"missing={sum(1 for r in rapport if r['status'] == 'missing')}")
    print(f"applied={bool(args.apply)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
