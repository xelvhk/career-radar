"""Typed domain errors for the local Opportunity Inbox boundary."""


class OpportunityError(ValueError):
    """Base class for expected Opportunity Inbox failures."""


class OpportunityInputError(OpportunityError):
    """The caller supplied invalid opportunity data or filters."""


class OpportunityNotFoundError(OpportunityError):
    """The requested opportunity does not exist."""


class OpportunityStorageError(OpportunityError):
    """The local Opportunity Inbox cannot be read or written safely."""
