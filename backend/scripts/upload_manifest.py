"""Upload manifest recordings through the same POST /upload hardware contract."""

import json
import mimetypes
import sys
from datetime import datetime
from pathlib import Path

import requests


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    manifest_path = project_root / "sample-recordings" / "manifest.json"
    recordings_dir = manifest_path.parent
    api_url = "http://localhost:8000/upload"
    if len(sys.argv) > 1:
        api_url = sys.argv[1].rstrip("/") + "/upload"

    entries = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in entries:
        audio_path = recordings_dir / entry["filename"]
        if not audio_path.is_file():
            raise FileNotFoundError(f"Manifest audio file not found: {audio_path}")
        recorded_at = datetime.fromisoformat(entry["recorded_at"])
        if recorded_at.tzinfo is None:
            raise ValueError(f"Manifest recorded_at must include a timezone: {entry['recorded_at']}")
        fields = {
            "device_id": str(entry["device_id"]),
            "recorded_at": entry["recorded_at"],
            "duration_ms": str(entry["duration_ms"]),
            "battery_pct": "" if entry.get("battery_pct") is None else str(entry["battery_pct"]),
        }
        content_type = mimetypes.guess_type(audio_path.name)[0] or "audio/wav"
        with audio_path.open("rb") as audio_file:
            response = requests.post(
                api_url,
                data=fields,
                files={"audio": (audio_path.name, audio_file, content_type)},
                timeout=120,
            )
        response.raise_for_status()
        print(response.json())


if __name__ == "__main__":
    main()
