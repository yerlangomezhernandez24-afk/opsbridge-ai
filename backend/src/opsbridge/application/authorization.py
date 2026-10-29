"""Server-side RBAC, ownership, and separation-of-duties policies."""

from dataclasses import dataclass
from enum import StrEnum

from opsbridge.domain.identity import LocalUser, UserId
from opsbridge.domain.tickets import ActorRole, Ticket, TicketStatus


class Permission(StrEnum):
    TICKET_CREATE = "ticket:create"
    TICKET_VIEW = "ticket:view"
    TICKET_MODIFY = "ticket:modify"
    TICKET_WORK = "ticket:work"
    ACTION_APPROVE = "action:approve"


ROLE_PERMISSIONS: dict[ActorRole, frozenset[Permission]] = {
    ActorRole.REQUESTER: frozenset(
        {Permission.TICKET_CREATE, Permission.TICKET_VIEW, Permission.TICKET_MODIFY}
    ),
    ActorRole.TECHNICIAN: frozenset(
        {
            Permission.TICKET_CREATE,
            Permission.TICKET_VIEW,
            Permission.TICKET_MODIFY,
            Permission.TICKET_WORK,
        }
    ),
    ActorRole.APPROVER: frozenset({Permission.TICKET_VIEW, Permission.ACTION_APPROVE}),
    ActorRole.AUTOMATION: frozenset(),
}


@dataclass(frozen=True, slots=True)
class ApprovalParties:
    requester_id: UserId
    proposer_id: UserId


class AuthorizationPolicy:
    """Deny by default and evaluate both role and resource relationship."""

    @staticmethod
    def permissions_for(user: LocalUser) -> frozenset[Permission]:
        if not user.is_active:
            return frozenset()
        return ROLE_PERMISSIONS.get(user.role, frozenset())

    def can_create_ticket(self, user: LocalUser) -> bool:
        return Permission.TICKET_CREATE in self.permissions_for(user)

    def can_view_ticket(self, user: LocalUser, ticket: Ticket) -> bool:
        if Permission.TICKET_VIEW not in self.permissions_for(user):
            return False
        if user.role is ActorRole.REQUESTER:
            return ticket.requester_id == user.actor_id
        return user.role in {ActorRole.TECHNICIAN, ActorRole.APPROVER}

    def can_modify_ticket(self, user: LocalUser, ticket: Ticket) -> bool:
        if Permission.TICKET_MODIFY not in self.permissions_for(user):
            return False
        if user.role is ActorRole.TECHNICIAN:
            return True
        return (
            user.role is ActorRole.REQUESTER
            and ticket.requester_id == user.actor_id
            and ticket.status is TicketStatus.NEW
        )

    def can_work_ticket(self, user: LocalUser, ticket: Ticket) -> bool:
        return (
            Permission.TICKET_WORK in self.permissions_for(user)
            and user.role is ActorRole.TECHNICIAN
            and ticket.assignee_id == user.actor_id
        )

    def can_approve(self, user: LocalUser, parties: ApprovalParties) -> bool:
        return (
            Permission.ACTION_APPROVE in self.permissions_for(user)
            and user.role is ActorRole.APPROVER
            and user.id not in {parties.requester_id, parties.proposer_id}
        )
