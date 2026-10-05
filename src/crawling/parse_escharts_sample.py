from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re
import argparse

from bs4 import BeautifulSoup

PROJECT_DIR = Path(__file__).resolve().parents[2]
SAMPLE_DIR = PROJECT_DIR / "data" / "raw" / "escharts" / "manual_samples"
METADATA_PATH = SAMPLE_DIR / "blasttv_paris_major_2023.metadata.json"

LABELS = {
    "peak_viewers": "Peak Viewers",
    "average_viewers": "Average Viewers",
    "hours_watched": "Hours Watched",
    "airtime_hours": "Airtime",
}


def read_metric(soup, label):
    """Đọc giá trị trong card có nhãn đã xác định."""
    candidates = []

    for node in soup.select("span[data-before]"):
        if node.get("data-before") != label:
            continue

        card = node.parent.parent
        value_node = card.select_one("span.font-bold.text-default")

        if value_node is not None:
            candidates.append(value_node.get_text(" ", strip=True))

    if len(candidates) != 1:
        raise ValueError(f"{label}: cần đúng 1 giá trị, tìm thấy {len(candidates)}.")

    return candidates[0]


def parse_integer(raw):
    # Hỗ trợ dấu cách thường, NBSP và narrow NBSP.
    compact = re.sub(r"\s+", "", raw)

    if not re.fullmatch(r"\d+", compact):
        raise ValueError(f"Không đọc được số nguyên đầy đủ: {raw!r}")

    return int(compact)


def parse_airtime(raw):
    match = re.fullmatch(
        r"\s*(\d+(?:\.\d+)?)\s*h" r"(?:\s*(\d+)\s*m)?\s*",
        raw,
        flags=re.IGNORECASE,
    )

    if not match:
        raise ValueError(f"Chưa hỗ trợ định dạng airtime: {raw!r}")

    hours = float(match.group(1))
    minutes = int(match.group(2) or 0)

    if minutes >= 60:
        raise ValueError(f"Số phút không hợp lệ: {raw!r}")

    return hours + minutes / 60


def main():
    parser = argparse.ArgumentParser(
        description="Parse và kiểm tra một mẫu Charts đã lưu offline."
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=METADATA_PATH,
    )
    args = parser.parse_args()

    metadata_path = args.metadata.resolve()

    metadata = json.loads(
        metadata_path.read_text(encoding="utf-8-sig")
    )

    sample_dir = metadata_path.parent
    html_path = sample_dir / metadata["html_file"]
    screenshot_path = sample_dir / metadata["screenshot_file"]

    if not html_path.is_file():
        raise FileNotFoundError(f"Không thấy HTML: {html_path}")

    if not screenshot_path.is_file():
        raise FileNotFoundError(f"Không thấy ảnh bằng chứng: {screenshot_path}")

    collected_at = metadata.get("collected_at")
    if not collected_at:
        raise ValueError("Metadata chưa có collected_at.")

    collected_time = datetime.fromisoformat(collected_at)
    if collected_time.tzinfo is None:
        raise ValueError("collected_at phải có múi giờ.")

    html_bytes = html_path.read_bytes()
    soup = BeautifulSoup(html_bytes, "html.parser")

    heading = soup.find("h1")
    if heading is None:
        raise ValueError("Không tìm thấy tiêu đề giải.")

    event_name_raw = heading.get_text(" ", strip=True)

    raw_metrics = {field: read_metric(soup, label) for field, label in LABELS.items()}

    # Giá trị được đọc từ HTML, không lấy từ metadata.
    metrics = {
        field: (parse_airtime(raw) if field == "airtime_hours" else parse_integer(raw))
        for field, raw in raw_metrics.items()
    }

    if metrics["peak_viewers"] < metrics["average_viewers"]:
        raise ValueError("Peak viewers nhỏ hơn average viewers.")

    if metrics["airtime_hours"] <= 0:
        raise ValueError("Airtime phải lớn hơn 0.")

    about = parse_about(soup)

    # Các giá trị này đều được đọc từ HTML.
    extracted_values = {
        **metrics,
        "prize_pool_usd": about["prize_pool_usd"],
        "start_date": about["start_date"],
        "end_date": about["end_date"],
    }

    # Metadata chỉ dùng để đối chiếu.
    references = metadata["reference_values_from_screenshot"]

    print("Giải:", event_name_raw)
    print("\nĐỐI CHIẾU HTML VỚI ẢNH")

    differences = []

    for field, extracted in extracted_values.items():
        expected = references[field]

        if expected is None:
            raise ValueError(
                f"Chưa nhập giá trị đối chiếu từ ảnh: {field}"
            )

        if isinstance(extracted, (int, float)) and isinstance(
            expected, (int, float)
        ):
            matched = abs(extracted - expected) <= 0.000001
        else:
            matched = extracted == expected

        print(
            f"{field}: HTML={extracted} | "
            f"Ảnh={expected} | {'OK' if matched else 'KHÁC'}"
        )

        if not matched:
            differences.append(field)

    if differences:
        raise ValueError(
            f"Chưa xuất mẫu: các trường khác ảnh {differences}"
        )

    parsed_at = datetime.now(timezone.utc).isoformat()

    record = {
        "source_site": "escharts",
        "source_url": metadata["source_url"],
        "collection_method": metadata["collection_method"],
        "collected_at": collected_at,
        "parsed_at": parsed_at,
        "event_name_raw": event_name_raw,
        "game_family": metadata["game_family"],
        "game_version": metadata["game_version"],
        "game_version_origin": "manual_metadata",
        "version_evidence": metadata.get("version_evidence"),
        "earnings_tournament_id_candidate": metadata[
            "earnings_tournament_id_candidate"
        ],
        "mapping_status": metadata["mapping_status"],
        "html_sha256": hashlib.sha256(html_bytes).hexdigest(),
        "source_html_file": html_path.relative_to(PROJECT_DIR).as_posix(),
        "source_screenshot_file": screenshot_path.relative_to(PROJECT_DIR).as_posix(),
        "raw_metrics": raw_metrics,
        **metrics,
        **about,
        "validation_status": "matches_screenshot_reference",
        "dataset_stage": "parsed_sample_not_final",
    }

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_dir = SAMPLE_DIR / "parsed"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"viewership_sample_{run_id}.json"

    output_path.write_text(
        json.dumps(record, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nĐã xuất:", output_path)
    print("Chỉ kiểm thử 1 mẫu; chưa phải dataset Charts hoàn chỉnh.")


def read_about_cell(soup, label, required=False):
    matches = []

    for row in soup.select("tr"):
        cells = row.find_all("td", recursive=False)

        if len(cells) != 2:
            continue

        if cells[0].get_text(" ", strip=True) == label:
            matches.append(cells[1])

    if len(matches) > 1:
        raise ValueError(f"Nhãn thông tin bị trùng: {label}")

    if not matches:
        if required:
            raise ValueError(f"Không tìm thấy trường bắt buộc: {label}")
        return None

    return matches[0]


def cell_text(cell):
    return cell.get_text(" ", strip=True) if cell else None


def parse_event_dates(raw):
    dates = re.findall(r"\b\d{2}\.\d{2}\.\d{2}(?:\d{2})?\b", raw)

    if len(dates) not in {1, 2}:
        raise ValueError(f"Chưa hỗ trợ chuỗi ngày: {raw!r}")

    def convert(value):
        pattern = "%d.%m.%Y" if len(value) == 10 else "%d.%m.%y"
        return datetime.strptime(value, pattern).date()

    start = convert(dates[0])
    end = convert(dates[-1])

    if start > end:
        raise ValueError(f"Ngày bắt đầu lớn hơn ngày kết thúc: {raw}")

    return start.isoformat(), end.isoformat()


def parse_displayed_usd(raw):
    compact = re.sub(r"\s+", "", raw)

    # Chỉ hỗ trợ dạng USD hiển thị đầy đủ trong mẫu này.
    # Không tự chuyển K/M hoặc tiền tệ khác.
    if not re.fullmatch(r"\$\d+(?:\.\d{1,2})?", compact):
        raise ValueError(f"Chưa hỗ trợ định dạng quỹ thưởng: {raw!r}")

    return float(compact[1:])


def parse_about(soup):
    date_cell = read_about_cell(soup, "Date:", required=True)
    prize_cell = read_about_cell(soup, "Prize Pool:", required=True)
    type_cell = read_about_cell(soup, "Type:")
    organizer_cell = read_about_cell(soup, "Organizers:")
    venue_cell = read_about_cell(soup, "Venue:")
    discipline_cell = read_about_cell(soup, "Discipline:")

    date_raw = cell_text(date_cell)
    start_date, end_date = parse_event_dates(date_raw)
    prize_pool_raw = cell_text(prize_cell)

    organizers = []
    if organizer_cell is not None:
        organizers = list(
            dict.fromkeys(
                link.get_text(" ", strip=True)
                for link in organizer_cell.select("a[href]")
                if link.get_text(" ", strip=True)
            )
        )

    # Chỉ đọc cờ trong Type/Venue, không đọc cờ của đội hoặc player.
    host_codes = set()

    for cell in [type_cell, venue_cell]:
        if cell is None:
            continue

        for image in cell.select("img[alt]"):
            code = image.get("alt", "").strip()

            if re.fullmatch(r"[a-zA-Z]{2}", code):
                host_codes.add(code.upper())

    # Không ép thành một quốc gia nếu nguồn có nhiều cờ khác nhau.
    host_country_code = next(iter(host_codes)) if len(host_codes) == 1 else None

    return {
        "date_raw": date_raw,
        "start_date": start_date,
        "end_date": end_date,
        "prize_pool_raw": prize_pool_raw,
        "prize_pool_usd": parse_displayed_usd(prize_pool_raw),
        "discipline_raw": cell_text(discipline_cell),
        "event_type_raw": cell_text(type_cell),
        "organizers_raw": organizers,
        "venue_raw": cell_text(venue_cell),
        "host_country_code": host_country_code,
        "host_country_codes_from_flags": sorted(host_codes),
    }


if __name__ == "__main__":
    main()
