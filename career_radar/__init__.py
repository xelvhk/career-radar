"""Career Radar's evidence-first data contracts."""

from .matching import MatchReport, analyze_vacancy
from .matching_config import load_matching_config
from .validation import ValidationIssue, load_yaml, validate_dataset

__all__ = [
    "MatchReport",
    "ValidationIssue",
    "analyze_vacancy",
    "load_matching_config",
    "load_yaml",
    "validate_dataset",
]
