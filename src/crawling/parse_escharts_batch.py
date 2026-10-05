from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit
import argparse
import json
import subprocess
import sys

PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = PROJECT_DIR / "data/raw/escharts/manual_samples"
PARSER_PATH = PROJECT_DIR / "src/crawling/parse_escharts_sample.py"
OUTPUT_ROOT = PROJECT_DIR / "data/raw/escharts/batch_parsed"

EXPECTED_FAMILIES = {
    "Counter-Strike",
    "Dota 2",
    "League of Legends",
    "Valorant",
}


def normalize_url(value):
    parts = urlsplit(value.strip())

    if parts.scheme != "https" or parts.hostname != "escharts.com":
        raise ValueError("source_url phải là URL HTTPS của escharts.com.")

    if not parts.path.startswith("/tournaments/"):
        raise ValueError("source_url phải trỏ tới trang giải.")

    return urlunsplit((
        "https",
        "escharts.com",
        parts.path.rstrip("/"),
        "",
        "",
    ))


def main():
    parser = argparse.ArgumentParser(
        description="Parse hàng loạt mẫu Charts đã lưu; không gọi mạng."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    metadata_files = sorted(input_dir.glob("*.metadata.json"))

    if not metadata_files:
        raise SystemExit(f"Không thấy metadata trong: {input_dir}")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_dir = OUTPUT_ROOT / run_id
    output_dir.mkdir(parents=True, exist_ok=False)

    records = []
    audit = []
    seen_urls = set()

    for index, metadata_path in enumerate(metadata_files, start=1):
        item = {
            "metadata_file": str(metadata_path),
            "source_url": None,
            "status": "failed",
            "error": None,
        }

        print(f"\n[{index}/{len(metadata_files)}] {metadata_path.name}")

        try:
            metadata = json.loads(
                metadata_path.read_text(encoding="utf-8-sig")
            )
            source_url = normalize_url(metadata["source_url"])
            item["source_url"] = source_url

            if source_url in seen_urls:
                raise ValueError(
                    "Trùng URL nguồn: cần kiểm tra các metadata trùng "
                    "trước khi chọn bản sử dụng."
                )

            seen_urls.add(source_url)

            if metadata["game_family"] not in EXPECTED_FAMILIES:
                raise ValueError("game_family nằm ngoài 4 nhóm đã chốt.")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    "-u",
                    str(PARSER_PATH),
                    "--metadata",
                    str(metadata_path),
                ],
                cwd=PROJECT_DIR,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                check=False,
            )

            log = (
                completed.stdout
                + "\n--- STDERR ---\n"
                + completed.stderr
            )
            log_path = output_dir / f"{index:04d}.log"
            log_path.write_text(log, encoding="utf-8")
            item["log_file"] = str(log_path)

            if completed.returncode != 0:
                raise ValueError(
                    f"Parser thất bại; xem log: {log_path}"
                )

            exported_paths = [
                line.split("Đã xuất:", 1)[1].strip()
                for line in completed.stdout.splitlines()
                if line.startswith("Đã xuất:")
            ]

            if len(exported_paths) != 1:
                raise ValueError("Không xác định được JSON parser đã xuất.")

            parsed_path = Path(exported_paths[0])
            record = json.loads(
                parsed_path.read_text(encoding="utf-8-sig")
            )

            if normalize_url(record["source_url"]) != source_url:
                raise ValueError("URL đầu ra không khớp metadata.")

            record["source_url"] = source_url
            record["source_metadata_file"] = str(metadata_path)
            records.append(record)

            item["status"] = "passed"
            item["parsed_file"] = str(parsed_path)
            print("PASS:", record["event_name_raw"])

        except Exception as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"
            print("FAIL:", item["error"])

        audit.append(item)

    passed_families = {record["game_family"] for record in records}
    missing_families = sorted(EXPECTED_FAMILIES - passed_families)
    failed_count = sum(item["status"] == "failed" for item in audit)

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_stage": "validated_samples_not_final_dataset",
        "metadata_count": len(metadata_files),
        "passed_count": len(records),
        "failed_count": failed_count,
        "passed_families": sorted(passed_families),
        "missing_families": missing_families,
    }

    outputs = {
        "viewership_samples.json": records,
        "parse_audit.json": audit,
        "summary.json": summary,
    }

    for filename, value in outputs.items():
        (output_dir / filename).write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print("\nKẾT QUẢ")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("Thư mục xuất:", output_dir)
    print("Đây là tập mẫu kiểm thử, chưa phải dataset Charts hoàn chỉnh.")

    if failed_count or missing_families:
        raise SystemExit(1)


if __name__ == "__main__":
    main()