import json
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "data" / "taxonomy.json"
TAXONOMY: dict = json.loads(_PATH.read_text())
TAXONOMY_VERSION: str = TAXONOMY["version"]


def skill_label(skill_id: str) -> str:
    return TAXONOMY["skills"].get(skill_id, {}).get("label", skill_id)


def related(skill_id: str) -> list[str]:
    return TAXONOMY["skills"].get(skill_id, {}).get("related", [])


def job_families(stream: str) -> dict:
    return TAXONOMY["job_families"].get(stream, {})


def all_job_families() -> dict:
    return TAXONOMY["job_families"]
