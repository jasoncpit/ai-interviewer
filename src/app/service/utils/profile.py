from __future__ import annotations

from typing import Dict, List


def derive_skills_from_profile(profile: Dict) -> List[str]:
    skills: List[str] = []
    for entry in profile.get("SKILLS", []):
        taxonomy_id = entry.get("taxonomy_id")
        if taxonomy_id:
            skill = taxonomy_id.split("/")[-1].lower()
            skills.append(skill)
    return skills or ["general"]


def build_spans_map_from_profile(profile: Dict) -> Dict[str, List[str]]:
    spans: Dict[str, List[str]] = {}
    for entry in profile.get("SKILLS", []):
        taxonomy_id = entry.get("taxonomy_id")
        if not taxonomy_id:
            continue
        skill = taxonomy_id.split("/")[-1].lower()
        evidence_sources = entry.get("evidence_sources", [])
        spans[skill] = [source.get("span", "") for source in evidence_sources]
    return spans
