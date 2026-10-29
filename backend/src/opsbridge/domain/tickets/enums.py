"""Closed vocabularies approved for the ticket domain."""

from enum import StrEnum


class TicketStatus(StrEnum):
    NEW = "new"
    TRIAGED = "triaged"
    IN_PROGRESS = "in_progress"
    WAITING_APPROVAL = "waiting_approval"
    WAITING_REQUESTER = "waiting_requester"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class TicketCategory(StrEnum):
    NETWORK_VPN = "network.vpn"
    SOFTWARE_APPLICATION = "software.application"
    HARDWARE_ENDPOINT = "hardware.endpoint"
    ACCESS_APPLICATION = "access.application"


class TicketPriority(StrEnum):
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"
    P4 = "p4"


class TicketImpact(StrEnum):
    SINGLE_USER = "single_user"
    MULTIPLE_USERS = "multiple_users"
    ORGANIZATION = "organization"


class TicketUrgency(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ActorRole(StrEnum):
    REQUESTER = "requester"
    TECHNICIAN = "technician"
    APPROVER = "approver"
    AUTOMATION = "automation"
