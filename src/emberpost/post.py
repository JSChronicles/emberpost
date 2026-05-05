import argparse
import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from emberpost.pagerduty import PagerDutyClient
from emberpost.schedule_config import (
    Frequency,
    PagerDutyScheduleEntry,
    PagerDutyScheduleGroup,
    ScheduleConfig,
    load_schedule,
)
from emberpost.slack import SlackClient

__LOGGER__ = logging.getLogger(__name__)


@dataclass(frozen=True)
class OnCallAssignment:
    group_name: str
    slack_group_id: str | None
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
    pagerduty_client,
    slack_client,
    *,
    resolve_slack_users: bool = True,
    today: date | None = None,
) -> list[OnCallAssignment]:
    today = today or date.today()
    assignments: list[OnCallAssignment] = []
    schedule_ids = [
        schedule.schedule_id
        for group in config.pagerduty.schedule_groups.values()
        for schedule in group.entries
    ]
    oncalls_by_schedule_id = pagerduty_client.get_oncalls(schedule_ids)
    slack_ids_by_email: dict[str, str] = {}

    for group_name, group in config.pagerduty.schedule_groups.items():
        for schedule in entries_for_week(group, today):
            oncall = oncalls_by_schedule_id[schedule.schedule_id]
            email = str(oncall.email)
            assignment_needs_slack_user = (
                resolve_slack_users or group.slack_group_id is not None
            )
            if assignment_needs_slack_user and email not in slack_ids_by_email:
                slack_ids_by_email[email] = slack_client.get_user_id_by_email(
                    oncall.email
                )
            assignments.append(
                OnCallAssignment(
                    group_name=group_name,
                    slack_group_id=group.slack_group_id,
                    schedule=schedule,
                    pagerduty_name=oncall.name,
                    slack_user_id=slack_ids_by_email.get(email),
                )
            )

    return assignments


def entries_for_week(
    group: PagerDutyScheduleGroup, today: date
) -> list[PagerDutyScheduleEntry]:
    if group.swap_on_odd_weeks and today.isocalendar().week % 2 == 1:
        return [group.entries[1], group.entries[0]]
    return group.entries


def render(assignments: list[OnCallAssignment], *, for_topic: bool) -> str:
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


def dispatch(config: ScheduleConfig, frequency: Frequency, *, dry_run: bool) -> None:
    if config.suspended:
        __LOGGER__.info(f"{config.id} is suspended; skipping")
        return

    if config.schedule != frequency:
        __LOGGER__.info(
            f"{config.id} is scheduled for {config.schedule}; skipping {frequency}"
        )
        return

    pagerduty_client = PagerDutyClient(config.pagerduty.tenant)
    slack_client = SlackClient(config.slack.slack_space, config.slack.slack_channel_id)
    resolve_slack_users = not config.slack.set_channel_topic
    assignments = collect_assignments(
        config, pagerduty_client, slack_client, resolve_slack_users=resolve_slack_users
    )
    rendered = render(assignments, for_topic=config.slack.set_channel_topic)

    if config.message_header:
        rendered = f"{config.message_header}\n{rendered}"
    if config.message_footer:
        rendered = f"{rendered}\n{config.message_footer}"

    if dry_run:
        target = (
            "channel topic" if config.slack.set_channel_topic else "channel message"
        )
        print(
            f"(dry-run) Would update Slack {target} for {config.slack.slack_channel_id}:"
        )
        print(rendered)
        for slack_group_id, user_ids in slack_user_group_updates(assignments).items():
            print(
                f"(dry-run) Would update Slack user group "
                f"{slack_group_id}: {','.join(user_ids)}"
            )
        return

    if config.slack.set_channel_topic:
        slack_client.update_channel_topic(rendered)
    else:
        slack_client.post_message(rendered)

    for slack_group_id, user_ids in slack_user_group_updates(assignments).items():
        slack_client.update_user_group(slack_group_id, user_ids)


def dispatch_schedule_files(
    schedule_files: list[Path], frequency: Frequency, *, dry_run: bool
) -> None:
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dispatch PagerDuty on-call schedules to Slack."
    )
    parser.add_argument(
        "--schedule-file",
        nargs="+",
        type=Path,
        required=True,
        help="One or more schedule YAML files to process.",
    )
    parser.add_argument(
        "--frequency",
        choices=list(Frequency),
        required=True,
        help="Only process schedules matching this frequency.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve on-call users and print intended Slack changes without writing to Slack.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format=("%(levelname)-8s [%(filename)s:%(funcName)s:%(lineno)d] %(message)s"),
    )
    if args.log_level != "DEBUG":
        # Suppress HTTP request logs from the PagerDuty client at INFO.
        logging.getLogger("httpx").setLevel(logging.WARNING)

    dispatch_schedule_files(
        args.schedule_file, Frequency(args.frequency), dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
