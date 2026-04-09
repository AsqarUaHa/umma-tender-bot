"""Load Meirbek Uzakbayev's YouTube video catalog for prompt injection."""

import json
from pathlib import Path

_VIDEOS_PATH = Path(__file__).parent / "videos.json"


def _load() -> dict:
    with _VIDEOS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


_DATA = _load()


def video_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def format_catalog() -> str:
    """Return the video list formatted for injection into the system prompt."""
    lines = [
        f"Спикер — {_DATA['channel']}, YouTube арна: {_DATA['channel_url']}",
        "",
        "Тендер және бизнес тақырыбындағы видеолар тізімі:",
    ]
    for v in _DATA["videos"]:
        lines.append(f"- «{v['title']}» — {video_url(v['id'])}")
    return "\n".join(lines)


VIDEO_CATALOG = format_catalog()
