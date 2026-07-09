"""Compare local eval JSONL with a previous batch exposed by the backend API.

Usage:

    KYC_EMAIL=... KYC_PASSWORD=... python backend/scripts/compare_eval_with_api_batch.py \
      --api-url https://backend-production-60fbc.up.railway.app \
      --eval backend/evals/testset_eval_mock.jsonl \
      --latest
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def _request_json(url: str, method: str = "GET", token: str | None = None,
                  data: bytes | None = None, content_type: str | None = None,
                  insecure: bool = False):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    context = ssl._create_unverified_context() if insecure else None
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def _login(api_url: str, email: str, password: str, insecure: bool = False) -> str:
    body = urllib.parse.urlencode({"username": email, "password": password}).encode("utf-8")
    payload = _request_json(
        f"{api_url.rstrip('/')}/auth/login",
        method="POST",
        data=body,
        content_type="application/x-www-form-urlencoded",
        insecure=insecure,
    )
    return payload["access_token"]


def _load_eval(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        rows[row["naam"]] = row
    return rows


def _classify_delta(eval_wp: int | None, api_wp: int | None) -> str:
    if eval_wp == api_wp:
        return "same"
    if eval_wp is None and api_wp is not None:
        return "new_missing"
    if eval_wp is not None and api_wp is None:
        return "new_found"
    return "changed"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--eval", type=Path, required=True)
    parser.add_argument("--batch-id")
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--insecure", action="store_true",
                        help="Disable TLS verification for local certificate-store issues.")
    args = parser.parse_args()

    email = os.environ.get("KYC_EMAIL")
    password = os.environ.get("KYC_PASSWORD")
    if not email or not password:
        raise SystemExit("KYC_EMAIL en KYC_PASSWORD moeten gezet zijn")

    token = _login(args.api_url, email, password, insecure=args.insecure)
    batches = _request_json(f"{args.api_url.rstrip('/')}/batches", token=token,
                            insecure=args.insecure)
    if args.latest:
        if not batches:
            raise SystemExit("Geen batches gevonden via API")
        batch = batches[0]
    else:
        batch = next((b for b in batches if b["id"] == args.batch_id), None)
        if batch is None:
            raise SystemExit(f"Batch niet gevonden: {args.batch_id}")

    companies = _request_json(
        f"{args.api_url.rstrip('/')}/batches/{batch['id']}/companies",
        token=token,
        insecure=args.insecure,
    )
    eval_rows = _load_eval(args.eval)

    comparisons = []
    counts: dict[str, int] = {}
    for company in companies:
        name = company["naam"]
        eval_row = eval_rows.get(name)
        if not eval_row:
            continue
        delta_type = _classify_delta(eval_row["candidate_wp"], company.get("wp_kandidaat"))
        counts[delta_type] = counts.get(delta_type, 0) + 1
        comparisons.append({
            "naam": name,
            "eval_wp": eval_row["candidate_wp"],
            "api_wp": company.get("wp_kandidaat"),
            "expected_wp": eval_row["expected_wp"],
            "eval_error_type": eval_row["error_type"],
            "api_confidence_label": company.get("confidence_label"),
            "api_confidence_score": company.get("confidence_score"),
            "delta_type": delta_type,
        })

    print(json.dumps({
        "batch": batch,
        "matched_companies": len(comparisons),
        "delta_counts": counts,
        "differences": [c for c in comparisons if c["delta_type"] != "same"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        sys.stderr.write(exc.read().decode("utf-8", errors="replace") + "\n")
        raise
