"""Workflow engine — the 14-stage approval chain (design ``03`` §2).

Rules implemented:
  R-WF-01 one status per approval by the role owning the current step
  R-WF-02 acting user must hold ``next_role`` of the current status
  R-WF-03 reject/cancel require a reason
  R-WF-04 statuses 12 (Completed) and 13 (Cancelled) are terminal
  R-WF-05 status 14 (Rejected) re-enters the flow at the rejecting step
  R-WF-06 every transition writes ``approval_history`` + ``audit_event``
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.audit.services import write_audit
from apps.common.enums import WorkflowStatusCode
from apps.workflow.models import Approval, ApprovalHistory, WorkflowStatus


class WorkflowError(Exception):
    """Base class for workflow rule violations."""


class InvalidTransition(WorkflowError):
    pass


class RoleNotPermitted(WorkflowError):
    pass


class ReasonRequired(WorkflowError):
    pass


def user_has_role(user, role) -> bool:
    if role is None:
        return True
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return user.roles.filter(pk=role.pk).exists()


def _next_status(current: WorkflowStatus) -> WorkflowStatus:
    """Linear successor: status N -> N+1 (11 -> 12 Completed)."""
    is_id_card_done = current.id == WorkflowStatusCode.ID_CARD_DONE
    target_id = WorkflowStatusCode.COMPLETED if is_id_card_done else current.id + 1
    return WorkflowStatus.objects.get(pk=int(target_id))


@transaction.atomic
def advance(record, user, *, action: str = "approve", reason: str = "") -> WorkflowStatus:
    """Advance ``record`` one step. Returns the new status.

    ``action`` ∈ {approve, reject, cancel}. Status 14 (Rejected) is routed by
    :func:`reenter`; calling ``advance`` on a rejected record re-enters the flow.
    """
    current = record.status
    if current.terminal:
        raise InvalidTransition(f"status {current.id} is terminal (R-WF-04)")

    if action in ("reject", "cancel") and not reason.strip():
        raise ReasonRequired(f"reason required for {action} (R-WF-03)")

    if current.id == WorkflowStatusCode.REJECTED:
        if action != "approve":
            raise InvalidTransition("a rejected record can only re-enter the flow")
        return reenter(record, user, action=action)

    if not user_has_role(user, current.next_role):
        raise RoleNotPermitted(
            f"user lacks next_role {current.next_role_id} for status {current.id} (R-WF-02)"
        )

    if action == "approve":
        new_status = _next_status(current)
    elif action == "reject":
        new_status = WorkflowStatus.objects.get(pk=int(WorkflowStatusCode.REJECTED))
    elif action == "cancel":
        new_status = WorkflowStatus.objects.get(pk=int(WorkflowStatusCode.CANCELLED))
    else:
        raise WorkflowError(f"unknown action {action!r}")

    if action in ("reject", "cancel"):
        record.reject_reason = reason.strip()

    Approval.objects.create(
        training_record=record,
        current_status=current,
        step_no=record.approvals.count() + 1,
        assigned_role=current.next_role,
        action=action,
        reason=reason.strip(),
        acted_by=user if getattr(user, "is_authenticated", False) else None,
        acted_at=timezone.now(),
    )
    ApprovalHistory.objects.create(
        training_record=record,
        status=new_status,
        full_name=record.learner.full_name,
    )

    record.status = new_status
    record.save(update_fields=["status", "reject_reason", "updated_at"])

    write_audit(
        action=f"workflow.{action}",
        entity="training_record",
        entity_id=record.pk,
        actor=user,
        after={"status": new_status.id, "reason": reason.strip()},
    )
    return new_status


@transaction.atomic
def reenter(record, user, *, action: str = "approve") -> WorkflowStatus:
    """Re-enter the flow after a rejection (R-WF-05, gap G7).

    Restores the record to the status held before the most recent rejection."""
    if record.status_id != WorkflowStatusCode.REJECTED:
        raise InvalidTransition("record is not in Rejected status")

    last_reject = (
        Approval.objects.filter(training_record=record, action="reject")
        .order_by("-created_at", "-id")
        .first()
    )
    if last_reject is None:
        raise InvalidTransition("no rejection to re-enter from")

    target = last_reject.current_status
    record.status = target
    record.reject_reason = ""
    record.save(update_fields=["status", "reject_reason", "updated_at"])

    ApprovalHistory.objects.create(
        training_record=record, status=target, full_name=record.learner.full_name
    )
    write_audit(
        action="workflow.reenter",
        entity="training_record",
        entity_id=record.pk,
        actor=user,
        after={"status": target.id},
    )
    return record.status
