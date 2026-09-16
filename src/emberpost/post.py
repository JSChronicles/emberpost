import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

from emberpost.msteams import MSTeamsClient
from emberpost.pagerduty import PagerDutyClient
from emberpost.schedule_config import (
    Destination,
    DestinationProviderName,
    Frequency,
    MSTeamsProviderOptions,
    PagerDutyScheduleEntry,
    PagerDutyScheduleGroup,
    ScheduleConfig,
    SlackProviderOptions,
    load_schedule,
)
from emberpost.slack import SlackClient

__LOGGER__ = logging.getLogger(__name__)


class SlackClientProtocol(Protocol):
    """Slack client behavior needed to deliver schedule updates."""

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


class MSTeamsClientProtocol(Protocol):
    """Microsoft Teams client behavior needed to deliver schedule updates."""

    def post_message(self, message: str) -> None:
        """Post a message through a Microsoft Teams Workflow webhook."""
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
    """Resolved PagerDuty assignment and its effective destination."""

    group_name: str
    destination: Destination
    slack_group_id: str | None
    schedule: PagerDutyScheduleEntry
    pagerduty_name: str
    email: str

    def rendered_line(self, identity: str | None = None) -> str:
        """Render this assignment with a provider-appropriate identity."""
        return f"{self.schedule.label}: {identity or self.pagerduty_name}"


def collect_assignments(
    config: ScheduleConfig,
    pagerduty_client: PagerDutyClientProtocol,
    *,
    today: date | None = None,
) -> list[OnCallAssignment]:
    """Resolve PagerDuty schedules without provider-specific user lookups."""
    today = today or date.today()
    assignments: list[OnCallAssignment] = []
    schedule_ids = [
        schedule.schedule_id
        for group in config.schedule_groups.values()
        for schedule in group.entries
    ]
    oncalls_by_schedule_id = pagerduty_client.get_oncalls(schedule_ids)

    for group_name, group in config.schedule_groups.items():
        destination = group.resolve_destination(config.destination)
        for schedule in entries_for_week(group, today):
            oncall = oncalls_by_schedule_id[schedule.schedule_id]
            assignments.append(
                OnCallAssignment(
                    group_name=group_name,
                    destination=destination,
                    slack_group_id=group.slack_group_id,
                    schedule=schedule,
                    pagerduty_name=oncall.name,
                    email=oncall.email,
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


def render(
    assignments: list[OnCallAssignment],
    identities_by_email: Mapping[str, str] | None = None,
) -> str:
    """Render assignments using PagerDuty names or provider identities."""
    lines: list[str] = []
    current_group: str | None = None

    for assignment in assignments:
        if assignment.group_name != current_group:
            if lines:
                lines.append("")
            lines.append(assignment.group_name)
            current_group = assignment.group_name

        identity = (
            identities_by_email.get(assignment.email)
            if identities_by_email is not None
            else None
        )
        lines.append(assignment.rendered_line(identity))

    return "\n".join(lines)


def slack_user_group_updates(
    assignments: list[OnCallAssignment], identities_by_email: Mapping[str, str]
) -> dict[str, list[str]]:
    """Build deduplicated Slack user-group membership updates."""
    updates: dict[str, list[str]] = {}
    for assignment in assignments:
        if assignment.slack_group_id is None:
            continue
        slack_user_id = identities_by_email[assignment.email]
        user_ids = updates.setdefault(assignment.slack_group_id, [])
        if slack_user_id not in user_ids:
            user_ids.append(slack_user_id)
    return updates


def _group_assignments_by_destination(
    assignments: list[OnCallAssignment],
) -> dict[Destination, list[OnCallAssignment]]:
    """Group assignments by their effective provider destination."""
    assignments_by_destination: dict[Destination, list[OnCallAssignment]] = {}
    for assignment in assignments:
        assignments_by_destination.setdefault(assignment.destination, []).append(
            assignment
        )
    return assignments_by_destination


def _render_destination(
    config: ScheduleConfig,
    assignments: list[OnCallAssignment],
    identities_by_email: Mapping[str, str] | None = None,
) -> str:
    """Render assignments with the schedule-level header and footer."""
    rendered = render(assignments, identities_by_email)
    if config.message_header:
        rendered = f"{config.message_header}\n{rendered}"
    if config.message_footer:
        rendered = f"{rendered}\n{config.message_footer}"
    return rendered


def _resolve_slack_identities(
    assignments: list[OnCallAssignment],
    options: SlackProviderOptions,
    slack_client: SlackClientProtocol,
    cached_user_ids: dict[tuple[str, str], str],
) -> dict[str, str]:
    """Resolve the Slack identities needed for messages and user groups."""
    identities_by_email: dict[str, str] = {}
    for assignment in assignments:
        needs_slack_user = (
            not options.set_channel_topic or assignment.slack_group_id is not None
        )
        if not needs_slack_user:
            continue
        cache_key = (options.space, assignment.email)
        if cache_key not in cached_user_ids:
            cached_user_ids[cache_key] = slack_client.get_user_id_by_email(
                assignment.email
            )
        identities_by_email[assignment.email] = cached_user_ids[cache_key]
    return identities_by_email


def _dispatch_to_slack(
    config: ScheduleConfig,
    options: SlackProviderOptions,
    assignments: list[OnCallAssignment],
    slack_client: SlackClientProtocol,
    cached_user_ids: dict[tuple[str, str], str],
    *,
    dry_run: bool,
) -> None:
    """Render and deliver assignments to one Slack destination."""
    identities_by_email = _resolve_slack_identities(
        assignments, options, slack_client, cached_user_ids
    )
    rendered = _render_destination(
        config,
        assignments,
        (
            None
            if options.set_channel_topic
            else {
                email: f"<@{slack_user_id}>"
                for email, slack_user_id in identities_by_email.items()
            }
        ),
    )
    user_group_updates = slack_user_group_updates(assignments, identities_by_email)

    if dry_run:
        target = "channel topic" if options.set_channel_topic else "channel message"
        print(
            f"(dry-run) Would update Slack {target} for "
            f"{options.channel_id} in {options.space}:"
        )
        print(rendered)
        for slack_group_id, user_ids in user_group_updates.items():
            print(
                f"(dry-run) Would update Slack user group "
                f"{slack_group_id} in {options.space}: {','.join(user_ids)}"
            )
        return

    if options.set_channel_topic:
        slack_client.update_channel_topic(options.channel_id, rendered)
    else:
        slack_client.post_message(options.channel_id, rendered)

    for slack_group_id, user_ids in user_group_updates.items():
        slack_client.update_user_group(slack_group_id, user_ids)


def _dispatch_to_msteams(
    config: ScheduleConfig,
    options: MSTeamsProviderOptions,
    assignments: list[OnCallAssignment],
    *,
    dry_run: bool,
) -> None:
    """Render and deliver assignments through a Teams Workflow webhook."""
    rendered = _render_destination(config, assignments)
    msteams_client = MSTeamsClient(options.webhook_env)
    if dry_run:
        print(
            f"(dry-run) Would post Microsoft Teams message using {options.webhook_env}:"
        )
        print(rendered)
        return

    msteams_client.post_message(rendered)


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

    assignments = collect_assignments(config, PagerDutyClient(config.pagerduty_tenant))
    slack_clients: dict[str, SlackClientProtocol] = {}
    cached_slack_user_ids: dict[tuple[str, str], str] = {}

    for destination, destination_assignments in _group_assignments_by_destination(
        assignments
    ).items():
        if destination.provider.name is DestinationProviderName.slack:
            options = destination.provider.options
            if not isinstance(options, SlackProviderOptions):
                raise TypeError("Slack destination has invalid provider options")
            if options.space not in slack_clients:
                slack_clients[options.space] = SlackClient(options.space)
            _dispatch_to_slack(
                config,
                options,
                destination_assignments,
                slack_clients[options.space],
                cached_slack_user_ids,
                dry_run=dry_run,
            )
            continue

        options = destination.provider.options
        if not isinstance(options, MSTeamsProviderOptions):
            raise TypeError("Microsoft Teams destination has invalid provider options")
        _dispatch_to_msteams(config, options, destination_assignments, dry_run=dry_run)


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
