"""Construcción y fusión de habilidades tipadas (Skill) a partir de texto, IA o el candidato."""

from __future__ import annotations

from collections.abc import Iterable

from app.domain.models import SKILL_LEVEL_ORDER, Skill, SkillKind, SkillLevel
from app.domain.skills import normalize_skill, skill_kind, split_level


def make_skill(raw: str, kind: str | None = None, level: str | None = None, *, suggested: bool = False,
               evidence: str | None = None) -> Skill:
    """'Excel avanzado' -> Skill(Excel, herramienta, avanzado). El tipo sale del catálogo; si no está,
    se usa el indicado (IA/candidato) o 'herramienta' por defecto."""
    base, text_level = split_level(raw)
    name = normalize_skill(base)
    k = skill_kind(name) or (kind if kind in SkillKind._value2member_map_ else SkillKind.HERRAMIENTA)
    lv = level or text_level
    return Skill(name=name[:60], kind=SkillKind(k),
                 level=SkillLevel(lv) if lv in SkillLevel._value2member_map_ else None,
                 suggested=suggested, evidence=evidence)


def merge_skills(*groups: Iterable[Skill | str]) -> list[Skill]:
    """Une listas sin duplicados (por nombre). Si una trae nivel y otra no, se conserva el nivel; un nivel
    confirmado (no sugerido) gana sobre uno sugerido."""
    out: dict[str, Skill] = {}
    for group in groups:
        for item in group:
            sk = make_skill(item) if isinstance(item, str) else item
            key = sk.name.lower()
            cur = out.get(key)
            if cur is None:
                out[key] = sk.model_copy()
            elif sk.level and (cur.level is None or (cur.suggested and not sk.suggested)):
                cur.level, cur.suggested, cur.evidence = sk.level, sk.suggested, sk.evidence
    return list(out.values())


def level_rank(level: SkillLevel | str | None) -> int:
    return SKILL_LEVEL_ORDER.index(SkillLevel(level)) if level in SkillLevel._value2member_map_ else -1
