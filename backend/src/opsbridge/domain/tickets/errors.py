"""Typed failures raised by the ticket domain."""


class TicketDomainError(Exception):
    """Base error for ticket business-rule failures."""


class TicketValidationError(TicketDomainError, ValueError):
    """A ticket value does not satisfy a domain invariant."""


class InvalidIdentifierError(TicketValidationError):
    """A ticket or actor identifier is malformed."""


class InvalidCategoryError(TicketValidationError):
    """A category is outside the approved taxonomy."""


class InvalidPriorityInputError(TicketValidationError):
    """Impact or urgency is outside the approved policy."""


class InvalidTimestampError(TicketValidationError):
    """A timestamp is not UTC-aware or moves time backwards."""


class InvalidTransitionError(TicketDomainError):
    """The requested source-to-target state transition is not allowed."""


class TransitionPreconditionError(TicketDomainError):
    """An allowed transition is missing required business evidence."""


class UnauthorizedDomainOperationError(TicketDomainError):
    """The actor role cannot perform the requested domain operation."""


class StaleTicketVersionError(TicketDomainError):
    """The supplied optimistic-lock version is no longer current."""
