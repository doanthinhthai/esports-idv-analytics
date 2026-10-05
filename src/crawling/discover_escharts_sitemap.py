"""Discover public tournament URLs from published sitemaps, without bypassing blocks."""

import argparse
from collections import Counter, deque
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time
from urllib.parse import urlsplit, urlunsplit
import xml.etree.ElementTree as ET

import requests


PROJECT_DIR = Path(__file__).resolve().parents[2]
START_URL = "https://escharts.com/sitemap-index.xml"
USER_AGENT = "Esports-IDV-Student-Research/1.0"
MAX_BYTES = 10 * 1024 * 1024
FAMILIES = {
    "csgo": "Counter-Strike",
    "dota2": "Dota 2",
    "lol": "League of Legends",
    "valorant": "Valorant",
}


def same_site(url):
    parts = urlsplit(url)
    return (
        parts.scheme == "https"
        and parts.hostname == "escharts.com"
        and parts.port in (None, 443)
        and parts.username is None
        and parts.password is None
    )


def tournament(url):
    if not same_site(url):
        return None
    parts = urlsplit(url)
    segments = parts.path.strip("/").split("/")
    if len(segments) != 3 or segments[0] != "tournaments":
        return None
    family = FAMILIES.get(segments[1])
    if not family:
        return None
    canonical = urlunsplit(("https", "escharts.com", parts.path.rstrip("/"), "", ""))
    return canonical, family


def parse_sitemap(body):
    if body.startswith(b"\x1f\x8b"):
        # Limit decompression, too, rather than trusting compressed file size.
        import io
        with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
            body = stream.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise ValueError("XML vượt giới hạn 10 MiB.")
    if b"<!DOCTYPE" in body.upper() or b"<!ENTITY" in body.upper():
        raise ValueError("Không đọc XML chứa DTD/entity.")
    root = ET.fromstring(body)
    kind = root.tag.rsplit("}", 1)[-1]
    child_kind = {"sitemapindex": "sitemap", "urlset": "url"}.get(kind)
    if not child_kind:
        raise ValueError("Phản hồi không phải sitemapindex/urlset.")
    entries = []
    for child in root:
        if child.tag.rsplit("}", 1)[-1] != child_kind:
            continue
        fields = {item.tag.rsplit("}", 1)[-1]: (item.text or "").strip() for item in child}
        if fields.get("loc"):
            entries.append(fields)
    return kind, entries


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-sitemaps", type=int, default=20)
    parser.add_argument("--delay", type=float, default=2)
    args = parser.parse_args()
    if args.max_sitemaps < 1 or args.delay < 2:
        parser.error("max-sitemaps phải >= 1; delay phải >= 2 giây.")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = PROJECT_DIR / "data/raw/escharts/sitemap_discovery" / run_id
    output.mkdir(parents=True, exist_ok=False)
    pending = deque([START_URL])
    queued = {START_URL}
    audits = []
    records = {}
    skipped = []
    stop_reason = None

    with requests.Session() as session:
        session.headers["User-Agent"] = USER_AGENT
        while pending and len(audits) < args.max_sitemaps:
            if audits:
                time.sleep(args.delay)
            url = pending.popleft()
            audit = {"url": url, "status": "failed"}
            audits.append(audit)
            print(f"[{len(audits)}/{args.max_sitemaps}] {url}", flush=True)
            try:
                with session.get(url, timeout=(10, 30), allow_redirects=False, stream=True) as response:
                    audit.update(http_status=response.status_code,
                                 content_type=response.headers.get("Content-Type"),
                                 retry_after=response.headers.get("Retry-After"),
                                 redirect_location=response.headers.get("Location"))
                    chunks = []
                    size = 0
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise ValueError("Phản hồi vượt giới hạn 10 MiB.")
                        chunks.append(chunk)
                    body = b"".join(chunks)
                filename = f"response_{len(audits):03d}.bin"
                (output / filename).write_bytes(body)
                audit.update(response_file=filename, response_bytes=len(body),
                             sha256=hashlib.sha256(body).hexdigest())
                if audit["http_status"] != 200:
                    stop_reason = f"HTTP {audit['http_status']}; dừng, không retry hoặc vượt chặn."
                    audit["error"] = stop_reason
                    break
                if b"text/html" in (audit["content_type"] or "").lower().encode():
                    raise ValueError("Nhận HTML thay vì sitemap XML; không xử lý trang kiểm tra truy cập.")
                kind, entries = parse_sitemap(body)
                audit.update(status="parsed", kind=kind, entry_count=len(entries))
                for entry in entries:
                    location = entry["loc"]
                    if kind == "sitemapindex":
                        if not same_site(location):
                            skipped.append(location)
                        elif location not in queued:
                            queued.add(location)
                            pending.append(location)
                    else:
                        candidate = tournament(location)
                        if candidate:
                            canonical, family = candidate
                            item = records.setdefault(canonical, {
                                "source_site": "escharts", "source_url": canonical,
                                "game_family": family, "scope_hint": "unknown_date",
                                "mapping_status": "unmatched", "sitemap_urls": set(),
                            })
                            item["sitemap_urls"].add(url)
                print(f"  {kind}: {len(entries)} mục; {len(records)} URL giải duy nhất", flush=True)
            except (requests.RequestException, ValueError, ET.ParseError, OSError) as error:
                audit["error"] = str(error)
                stop_reason = str(error)
                break

    rows = []
    for _, item in sorted(records.items()):
        rows.append({**item, "sitemap_urls": " | ".join(sorted(item["sitemap_urls"]))})
    with (output / "tournament_urls.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "source_site", "source_url", "game_family", "scope_hint", "mapping_status", "sitemap_urls"
        ])
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "dataset_stage": "sitemap_discovery_not_verified_full_coverage",
        "requested_sitemap_count": len(audits),
        "parsed_sitemap_count": sum(item["status"] == "parsed" for item in audits),
        "unique_url_count": len(rows),
        "urls_by_family": dict(Counter(item["game_family"] for item in rows)),
        "pending_sitemap_count": len(pending),
        "skipped_external_sitemap_count": len(skipped),
        "queue_completed": not pending and stop_reason is None,
        "stop_reason": stop_reason,
        "note": "Chưa tải trang giải; lastmod không phải ngày tổ chức. Sitemap không chứng minh đủ nguồn hoặc đủ phạm vi 2012–2025.",
    }
    for name, data in [("summary.json", summary), ("sitemap_audit.json", audits),
                       ("pending_sitemaps.json", list(pending)), ("skipped_sitemaps.json", skipped)]:
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Thư mục kết quả:", output)
    print("Không sửa Earnings/SQLite; không tải trang chi tiết.")


if __name__ == "__main__":
    main()
