"""Evidence-aware, deterministic vacancy matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from .matching_config import MatchingConfig
from .vacancy import Vacancy, VacancyRequirement, parse_vacancy


EVIDENCE_CREDIT = {"public": 1.0, "on_request": 0.7, "private": 0.0, "gap": 0.0}
TECHNICAL_CREDIT = {
    "production": 1.0,
    "public_evidence": 1.0,
    "practical": 1.0,
    "knowledge": 0.35,
}
IMPORTANCE_WEIGHT = {"required": 1.0, "preferred": 0.5}
DISCLOSURE_RANK = {"gap": 0, "private": 1, "on_request": 2, "public": 3}


@dataclass(frozen=True, slots=True)
class RequirementMapping:
    skill_id: str
    skill_name: str
    importance: str
    skill_level: str
    evidence_status: str
    projects: tuple[str, ...]
    artifacts: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MatchDimension:
    name: str
    status: Literal["known", "unknown"]
    score: int | None
    weight: int
    reason: str


@dataclass(frozen=True, slots=True)
class MatchReport:
    vacancy: Vacancy
    dimensions: tuple[MatchDimension, ...]
    requirement_mappings: tuple[RequirementMapping, ...]
    required_gaps: tuple[str, ...]
    unverified_constraints: tuple[str, ...]
    overall_score: int
    confidence: int
    recommendation: Literal["APPLY", "REVIEW", "SKIP"]
    reasons: tuple[str, ...]


def analyze_vacancy(
    text: str,
    *,
    projects_data: dict[str, Any],
    skills_data: dict[str, Any],
    goals_data: dict[str, Any],
    config: MatchingConfig,
) -> MatchReport:
    vacancy = parse_vacancy(text, config)
    projects = {
        project["id"]: project for project in projects_data["projects"]
    }
    skills = {skill["id"]: skill for skill in skills_data["skills"]}
    mappings = tuple(
        _map_requirement(requirement, skills[requirement.skill_id], projects)
        for requirement in vacancy.requirements
    )
    goals = goals_data["career_goals"]
    dimensions = (
        _technical_dimension(vacancy.requirements, mappings, config),
        _evidence_dimension(vacancy.requirements, mappings, config),
        _direction_dimension(vacancy, goals, config),
        _domain_dimension(vacancy, goals, config),
        _seniority_dimension(vacancy, goals, config),
        _location_dimension(vacancy, goals, config),
        _unknown_dimension("salary", config, "salary data or preference is missing"),
    )
    known = [item for item in dimensions if item.status == "known"]
    known_weight = sum(item.weight for item in known)
    overall_score = (
        round(sum((item.score or 0) * item.weight for item in known) / known_weight)
        if known_weight
        else 0
    )
    confidence = known_weight
    if not vacancy.requirements:
        confidence = min(confidence, 30)
    confidence = max(0, confidence - min(40, 10 * len(vacancy.unmapped_requirement_lines)))

    required_gaps = tuple(
        item.skill_id
        for item in mappings
        if item.importance == "required" and item.evidence_status == "gap"
    )
    unverified_constraints = _unverified_constraints(vacancy, goals)
    recommendation, reasons = _recommend(
        overall_score,
        confidence,
        required_gaps,
        unverified_constraints,
        config,
    )
    return MatchReport(
        vacancy=vacancy,
        dimensions=dimensions,
        requirement_mappings=mappings,
        required_gaps=required_gaps,
        unverified_constraints=unverified_constraints,
        overall_score=overall_score,
        confidence=confidence,
        recommendation=recommendation,
        reasons=reasons,
    )


def _map_requirement(
    requirement: VacancyRequirement,
    skill: dict[str, Any],
    projects: dict[str, dict[str, Any]],
) -> RequirementMapping:
    status = "gap"
    artifact_labels: list[str] = []
    project_ids: list[str] = []
    for evidence in skill.get("evidence", []):
        project_id = evidence["project_id"]
        project = projects[project_id]
        artifacts = {item["path"]: item for item in project["artifacts"]}
        for artifact_path in evidence.get("artifacts", []):
            artifact = artifacts.get(artifact_path)
            if not artifact or artifact.get("verification") != "verified":
                continue
            disclosure = artifact["disclosure"]
            if (
                disclosure == "public"
                and project["repository_visibility"] != "public"
            ):
                disclosure = "private"
            if DISCLOSURE_RANK[disclosure] > DISCLOSURE_RANK[status]:
                status = disclosure
            if disclosure != "private":
                artifact_labels.append(f"{project_id}:{artifact_path} [{disclosure}]")
                project_ids.append(project_id)
    return RequirementMapping(
        skill_id=requirement.skill_id,
        skill_name=skill["name"],
        importance=requirement.importance,
        skill_level=skill["level"],
        evidence_status=status,
        projects=tuple(dict.fromkeys(project_ids)),
        artifacts=tuple(dict.fromkeys(artifact_labels)),
    )


def _technical_dimension(
    requirements: tuple[VacancyRequirement, ...],
    mappings: tuple[RequirementMapping, ...],
    config: MatchingConfig,
) -> MatchDimension:
    if not requirements:
        return _unknown_dimension("technical", config, "no cataloged skills extracted")
    score = _weighted_requirement_score(
        mappings, lambda item: TECHNICAL_CREDIT.get(item.skill_level, 0.0)
    )
    return _known_dimension("technical", score, config, "cataloged skill-level fit")


def _evidence_dimension(
    requirements: tuple[VacancyRequirement, ...],
    mappings: tuple[RequirementMapping, ...],
    config: MatchingConfig,
) -> MatchDimension:
    if not requirements:
        return _unknown_dimension("evidence", config, "no requirements to evidence-map")
    score = _weighted_requirement_score(
        mappings, lambda item: EVIDENCE_CREDIT[item.evidence_status]
    )
    return _known_dimension("evidence", score, config, "verified evidence disclosure coverage")


def _weighted_requirement_score(
    mappings: tuple[RequirementMapping, ...],
    credit: Callable[[RequirementMapping], float],
) -> int:
    denominator = sum(IMPORTANCE_WEIGHT[item.importance] for item in mappings)
    numerator = sum(
        IMPORTANCE_WEIGHT[item.importance] * credit(item) for item in mappings
    )
    return round(100 * numerator / denominator) if denominator else 0


def _direction_dimension(
    vacancy: Vacancy, goals: dict[str, Any], config: MatchingConfig
) -> MatchDimension:
    if not vacancy.target_roles:
        return _unknown_dimension("direction", config, "target role was not recognized")
    priorities = {item["id"]: item["priority"] for item in goals["target_roles"]}
    credit = {"high": 100, "medium": 70, "low": 40}
    score = max(credit[priorities[role]] for role in vacancy.target_roles if role in priorities)
    return _known_dimension("direction", score, config, "recognized target-role priority")


def _domain_dimension(
    vacancy: Vacancy, goals: dict[str, Any], config: MatchingConfig
) -> MatchDimension:
    if not vacancy.domains:
        return _unknown_dimension("domain", config, "vacancy domain was not recognized")
    preferred = set(goals.get("preferred_domains", []))
    score = round(100 * len(set(vacancy.domains) & preferred) / len(set(vacancy.domains)))
    return _known_dimension("domain", score, config, "preferred-domain overlap")


def _seniority_dimension(
    vacancy: Vacancy, goals: dict[str, Any], config: MatchingConfig
) -> MatchDimension:
    target = goals.get("target_seniority")
    if vacancy.seniority is None or not isinstance(target, list) or not target:
        return _unknown_dimension(
            "seniority", config, "vacancy seniority or target preference is missing"
        )
    score = 100 if vacancy.seniority in target else 0
    return _known_dimension("seniority", score, config, "target-seniority match")


def _location_dimension(
    vacancy: Vacancy, goals: dict[str, Any], config: MatchingConfig
) -> MatchDimension:
    if vacancy.is_remote is None:
        return _unknown_dimension("location", config, "work mode was not recognized")
    preference = goals.get("work_preferences", {}).get("remote")
    if preference not in {"preferred", "required", "not_preferred"}:
        return _unknown_dimension("location", config, "remote preference is missing")
    if vacancy.is_remote:
        score = 100 if preference in {"preferred", "required"} else 50
    else:
        score = 0 if preference == "required" else 40 if preference == "preferred" else 100
    return _known_dimension("location", score, config, "remote-work preference match")


def _known_dimension(
    name: str, score: int, config: MatchingConfig, reason: str
) -> MatchDimension:
    return MatchDimension(name, "known", score, config.weights[name], reason)


def _unknown_dimension(
    name: str, config: MatchingConfig, reason: str
) -> MatchDimension:
    return MatchDimension(name, "unknown", None, config.weights[name], reason)


def _recommend(
    score: int,
    confidence: int,
    required_gaps: tuple[str, ...],
    unverified_constraints: tuple[str, ...],
    config: MatchingConfig,
) -> tuple[Literal["APPLY", "REVIEW", "SKIP"], tuple[str, ...]]:
    if (
        score >= config.apply_score
        and confidence >= config.minimum_confidence
        and not required_gaps
        and not unverified_constraints
    ):
        return "APPLY", ("high match with sufficient confidence and no required gaps",)
    if unverified_constraints:
        reasons = ["mandatory career constraints are not verified"]
        if required_gaps:
            reasons.append("required skill gaps need human review")
        if confidence < config.minimum_confidence:
            reasons.append("confidence is below the automatic-decision threshold")
        return "REVIEW", tuple(reasons)
    if score < config.skip_score and confidence >= config.minimum_confidence:
        return "SKIP", ("low match with sufficient confidence",)
    reasons: list[str] = []
    if confidence < config.minimum_confidence:
        reasons.append("confidence is below the automatic-decision threshold")
    if required_gaps:
        reasons.append("required skill gaps need human review")
    if not reasons:
        reasons.append("match score is between automatic decision thresholds")
    return "REVIEW", tuple(reasons)


def _unverified_constraints(
    vacancy: Vacancy, goals: dict[str, Any]
) -> tuple[str, ...]:
    constraints: list[str] = []
    profile = goals.get("experience_profile", {})
    years = profile.get("commercial_years") if isinstance(profile, dict) else None
    if vacancy.minimum_years_experience is not None and (
        type(years) is not int or years < vacancy.minimum_years_experience
    ):
        constraints.append(
            f"minimum_years_experience:{vacancy.minimum_years_experience}"
        )
    has_production = (
        profile.get("verified_production_experience")
        if isinstance(profile, dict)
        else None
    )
    if vacancy.requires_production_experience and has_production is not True:
        constraints.append("production_experience")
    locations = goals.get("work_preferences", {}).get("current_country_codes")
    for constraint in vacancy.location_constraints:
        country = constraint.removeprefix("outside:")
        if not isinstance(locations, list) or country in locations:
            constraints.append(f"location:{constraint}")
    return tuple(constraints)
