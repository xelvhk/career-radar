"""Career Radar's evidence-first data contracts."""

from .collected_vacancy import (
    CollectedVacancy,
    CollectedVacancyInput,
    collected_vacancy_to_dict,
    normalize_collected_vacancy,
)
from .errors import (
    OpportunityError,
    OpportunityInputError,
    OpportunityNotFoundError,
    OpportunityStorageError,
)
from .matching import MatchReport, analyze_vacancy
from .matching_config import load_matching_config
from .opportunity_store import Opportunity, OpportunityStore, UpsertResult
from .validation import ValidationIssue, load_yaml, validate_dataset

__all__ = [
    "CollectedVacancy",
    "CollectedVacancyInput",
    "MatchReport",
    "Opportunity",
    "OpportunityError",
    "OpportunityInputError",
    "OpportunityNotFoundError",
    "OpportunityStore",
    "OpportunityStorageError",
    "UpsertResult",
    "ValidationIssue",
    "analyze_vacancy",
    "collected_vacancy_to_dict",
    "load_matching_config",
    "load_yaml",
    "normalize_collected_vacancy",
    "validate_dataset",
]
