import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from emberpost.pagerduty import PagerDutyClient
from emberpost.schedule_config import (
    Frequency,
    PagerDutyScheduleEntry,
    PagerDutyScheduleGroup,
    ScheduleConfig,
    SlackConfig,
    load_schedule,
)
from emberpost.slack import SlackClient

__LOGGER__ = logging.getLogger(__name__)


class SlackClientProtocol(Protocol):
    """Slack client behavior needed to prepare and deliver updates."""

    def get_user_id_by_email(self, email: str) -> str:
        """Return the Slack user ID associated with an email address."""
        ...

    def post_message(self, channel_id: str, message: str) -> None:
        """Post a message to a Slack channel."""
        ...

    def update_channel_topic(self, channel_id: str, topic: str) -> None:
        """Update a Slack channel topic."""
        ...

    def update_user_group(self, user_group_id: str, user_ids: list[str]) -> None:
        """Replace the members of a Slack user group."""
        ...


class PagerDutyOnCallProtocol(Protocol):
    """Resolved PagerDuty on-call identity used by Emberpost."""

    @property
    def email(self) -> str:
        """Return the on-call user's email address."""
        ...

    @property
    def name(self) -> str:
        """Return the on-call user's display name."""
        ...


class PagerDutyClientProtocol(Protocol):
    """PagerDuty client behavior needed to collect assignments."""

    def get_oncalls(
        self, schedule_ids: list[str]
    ) -> Mapping[str, PagerDutyOnCallProtocol]:
        """Return the current on-call identity for each schedule ID."""
        ...


@dataclass(frozen=True)
class OnCallAssignment:
    """Resolved PagerDuty assignment and its effective Slack destination."""

    group_name: str
    slack_group_id: str | None
    slack: SlackConfig
    schedule: PagerDutyScheduleEntry
    pagerduty_name: str
    slack_user_id: str | None

    @property
    def message_line(self) -> str:
        if self.slack_user_id is None:
            raise ValueError("Slack user ID is required to render a Slack mention")
        return f"{self.schedule.label}: <@{self.slack_user_id}>"

    @property
    def topic_line(self) -> str:
        return f"{self.schedule.label}: {self.pagerduty_name}"


def collect_assignments(
    config: ScheduleConfig,
    pagerduty_client: PagerDutyClientProtocol,
    slack_clients: Mapping[str, SlackClientProtocol],
    *,
    today: date | None = None,
) -> list[OnCallAssignment]:
    """Resolve PagerDuty schedules and their Slack user identities."""
    today = today or date.today()
    assignments: list[OnCallAssignment] = []
    schedule_ids = [
        schedule.schedule_id
        for group in config.pagerduty.schedule_groups.values()
        for schedule in group.entries
    ]
    oncalls_by_schedule_id = pagerduty_client.get_oncalls(schedule_ids)
    slack_ids_by_workspace_and_email: dict[tuple[str, str], str] = {}

    for group_name, group in config.pagerduty.schedule_groups.items():
        slack = group.resolve_slack_config(config.slack)
        slack_client = slack_clients[slack.slack_space]
        for schedule in entries_for_week(group, today):
            oncall = oncalls_by_schedule_id[schedule.schedule_id]
            email = str(oncall.email)
            assignment_needs_slack_user = (
                not slack.set_channel_topic or group.slack_group_id is not None
            )
            slack_user_key = (slack.slack_space, email)
            if (
                assignment_needs_slack_user
                and slack_user_key not in slack_ids_by_workspace_and_email
            ):
                slack_ids_by_workspace_and_email[slack_user_key] = (
                    slack_client.get_user_id_by_email(oncall.email)
                )
            assignments.append(
                OnCallAssignment(
                    group_name=group_name,
                    slack_group_id=group.slack_group_id,
                    slack=slack,
                    schedule=schedule,
                    pagerduty_name=oncall.name,
                    slack_user_id=slack_ids_by_workspace_and_email.get(slack_user_key),
                )
            )

    return assignments


def entries_for_week(
    group: PagerDutyScheduleGroup, today: date
) -> list[PagerDutyScheduleEntry]:
    """Return schedule entries in the order applicable to an ISO week."""
    if group.swap_on_odd_weeks and today.isocalendar().week % 2 == 1:
        return [group.entries[1], group.entries[0]]
    return group.entries


def render(assignments: list[OnCallAssignment], *, for_topic: bool) -> str:
    """Render assignments as a Slack message or channel topic."""
    lines: list[str] = []
    current_group: str | None = None

    for assignment in assignments:
        if assignment.group_name != current_group:
            if lines:
                lines.append("")
            lines.append(assignment.group_name)
            current_group = assignment.group_name

        lines.append(assignment.topic_line if for_topic else assignment.message_line)

    return "\n".join(lines)


def slack_user_group_updates(
    assignments: list[OnCallAssignment],
) -> dict[str, list[str]]:
    """Build deduplicated Slack user-group membership updates."""
    updates: dict[str, list[str]] = {}
    for assignment in assignments:
        if assignment.slack_group_id is None:
            continue
        if assignment.slack_user_id is None:
            raise ValueError("Slack user ID is required to update a Slack user group")
        user_ids = updates.setdefault(assignment.slack_group_id, [])
        if assignment.slack_user_id not in user_ids:
            user_ids.append(assignment.slack_user_id)
    return updates


def _group_assignments_by_destination(
    assignments: list[OnCallAssignment],
) -> dict[SlackConfig, list[OnCallAssignment]]:
    """Group assignments by their effective Slack destination."""
    assignments_by_destination: dict[SlackConfig, list[OnCallAssignment]] = {}
    for assignment in assignments:
        assignments_by_destination.setdefault(assignment.slack, []).append(assignment)
    return assignments_by_destination


def _render_destination(
    config: ScheduleConfig,
    destination: SlackConfig,
    assignments: list[OnCallAssignment],
) -> str:
    """Render assignments with the schedule-level header and footer."""
    rendered = render(assignments, for_topic=destination.set_channel_topic)
    if config.message_header:
        rendered = f"{config.message_header}\n{rendered}"
    if config.message_footer:
        rendered = f"{rendered}\n{config.message_footer}"
    return rendered


def _dispatch_to_destination(
    config: ScheduleConfig,
    destination: SlackConfig,
    assignments: list[OnCallAssignment],
    slack_client: SlackClientProtocol,
    *,
    dry_run: bool,
) -> None:
    """Deliver one rendered update and its Slack user-group changes."""
    rendered = _render_destination(config, destination, assignments)
    user_group_updates = slack_user_group_updates(assignments)

    if dry_run:
        target = "channel topic" if destination.set_channel_topic else "channel message"
        print(
            f"(dry-run) Would update Slack {target} for "
            f"{destination.slack_channel_id} in {destination.slack_space}:"
        )
        print(rendered)
        for slack_group_id, user_ids in user_group_updates.items():
            print(
                f"(dry-run) Would update Slack user group "
                f"{slack_group_id} in {destination.slack_space}: "
                f"{','.join(user_ids)}"
            )
        return

    if destination.set_channel_topic:
        slack_client.update_channel_topic(destination.slack_channel_id, rendered)
    else:
        slack_client.post_message(destination.slack_channel_id, rendered)

    for slack_group_id, user_ids in user_group_updates.items():
        slack_client.update_user_group(slack_group_id, user_ids)


def dispatch(config: ScheduleConfig, frequency: Frequency, *, dry_run: bool) -> None:
    """Dispatch one schedule configuration when its frequency matches."""
    if config.suspended:
        __LOGGER__.info(f"{config.id} is suspended; skipping")
        return

    if config.schedule != frequency:
        __LOGGER__.info(
            f"{config.id} is scheduled for {config.schedule}; skipping {frequency}"
        )
        return

    pagerduty_client = PagerDutyClient(config.pagerduty.tenant)
    slack_spaces = {
        group.resolve_slack_config(config.slack).slack_space
        for group in config.pagerduty.schedule_groups.values()
    }
    slack_clients = {
        slack_space: SlackClient(slack_space) for slack_space in sorted(slack_spaces)
    }
    assignments = collect_assignments(config, pagerduty_client, slack_clients)
    for destination, destination_assignments in _group_assignments_by_destination(
        assignments
    ).items():
        _dispatch_to_destination(
            config,
            destination,
            destination_assignments,
            slack_clients[destination.slack_space],
            dry_run=dry_run,
        )


def dispatch_schedule_files(
    schedule_files: list[Path], frequency: Frequency, *, dry_run: bool
) -> None:
    """Dispatch schedule files and report a combined operational failure."""
    failed = False

    for schedule_file in schedule_files:
        __LOGGER__.info(f"Processing {schedule_file}")
        try:
            config = load_schedule(schedule_file)
            dispatch(config, frequency, dry_run=dry_run)
        except Exception:
            __LOGGER__.exception(f"Error processing {schedule_file}")
            failed = True

    if failed:
        raise RuntimeError("One or more schedule files failed to process")
