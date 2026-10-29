"""Identity values, cryptography, and local authorization policy."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from opsbridge.application.authorization import ApprovalParties, AuthorizationPolicy, Permission
from opsbridge.domain.identity import IdentityValidationError, LocalUser, LoginId, UserId
from opsbridge.domain.tickets import (
    Actor,
    ActorRole,
    Ticket,
    TicketCategory,
    TicketId,
    TicketImpact,
    TicketKey,
    TicketUrgency,
)
from opsbridge.infrastructure.security import Argon2PasswordService, OpaqueTokenService

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def _user(value: str, role: ActorRole, *, active: bool = True) -> LocalUser:
    return LocalUser(
        id=UserId(UUID(value)),
        login_id=LoginId.parse(f"user-{value[-4:]}"),
        display_name="Local User",
        role=role,
        is_active=active,
        created_at=NOW,
        updated_at=NOW,
    )


def _ticket(requester: LocalUser) -> Ticket:
    return Ticket.create(
        ticket_id=TicketId(UUID("00000000-0000-4000-8000-000000000099")),
        key=TicketKey("OPS-2026-000099"),
        title="Authorization sample",
        description="A ticket used to verify horizontal authorization rules.",
        category=TicketCategory.NETWORK_VPN,
        impact=TicketImpact.SINGLE_USER,
        urgency=TicketUrgency.MEDIUM,
        requester=Actor(requester.actor_id, ActorRole.REQUESTER),
        created_at=NOW,
    )


def test_login_id_is_normalized_and_rejects_invalid_values() -> None:
    assert str(LoginId.parse("  Alice.Example  ")) == "alice.example"
    with pytest.raises(IdentityValidationError):
        LoginId.parse("a")


def test_argon2id_hash_is_salted_and_verifiable() -> None:
    passwords = Argon2PasswordService()
    first = passwords.hash("correct horse battery staple")
    second = passwords.hash("correct horse battery staple")

    assert first.startswith("$argon2id$")
    assert first != second
    assert passwords.verify(first, "correct horse battery staple")
    assert not passwords.verify(first, "wrong password")
    assert not passwords.verify(None, "wrong password")


def test_opaque_tokens_are_not_equal_to_persisted_verifiers() -> None:
    tokens = OpaqueTokenService()
    raw = tokens.issue()

    assert len(raw) >= 43
    assert tokens.verifier(raw) != raw
    assert tokens.csrf_matches(raw, tokens.csrf_token(raw))
    assert not tokens.csrf_matches(raw, "incorrect")


def test_rbac_denies_horizontal_access_and_self_approval() -> None:
    requester = _user("00000000-0000-4000-8000-000000000001", ActorRole.REQUESTER)
    other = _user("00000000-0000-4000-8000-000000000002", ActorRole.REQUESTER)
    approver = _user("00000000-0000-4000-8000-000000000003", ActorRole.APPROVER)
    ticket = _ticket(requester)
    policy = AuthorizationPolicy()

    assert policy.can_view_ticket(requester, ticket)
    assert not policy.can_view_ticket(other, ticket)
    assert not policy.can_work_ticket(requester, ticket)
    assert not policy.can_approve(
        approver,
        ApprovalParties(requester_id=requester.id, proposer_id=approver.id),
    )
    assert Permission.TICKET_CREATE not in policy.permissions_for(
        _user("00000000-0000-4000-8000-000000000004", ActorRole.APPROVER)
    )


def test_disabled_user_has_no_permissions() -> None:
    disabled = _user(
        "00000000-0000-4000-8000-000000000005",
        ActorRole.TECHNICIAN,
        active=False,
    )
    assert AuthorizationPolicy().permissions_for(disabled) == frozenset()
