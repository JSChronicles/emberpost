import json
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

import jsonschema
import yaml


SCHEMA_FILE = "schedule.schema.json"


class Frequency(StrEnum):
    """Supported schedule dispatch frequencies."""

    daily = "daily"
    weekly = "weekly"
    manual = "manual"


@dataclass(frozen=True)
class PagerDutyScheduleEntry:
    """One labeled PagerDuty schedule to resolve."""

    schedule_id: str
    label: str

    @classmethod
    def from_dict(cls, config: dict) -> "PagerDutyScheduleEntry":
        return cls(schedule_id=config["schedule_id"], label=config["label"])


@dataclass(frozen=True)
class SlackConfig:
    """Effective Slack workspace, channel, and delivery mode."""

    slack_space: str
    slack_channel_id: str
    set_channel_topic: bool = False

    @classmethod
    def from_dict(cls, config: dict) -> "SlackConfig":
        return cls(
            slack_space=config["slack_space"],
            slack_channel_id=config["slack_channel_id"],
            set_channel_topic=config.get("set_channel_topic", False),
        )


@dataclass(frozen=True)
class PagerDutyScheduleGroup:
    """A named schedule group with optional Slack destination overrides."""

    entries: list[PagerDutyScheduleEntry]
    slack_group_id: str | None = None
    slack_space: str | None = None
    slack_channel_id: str | None = None
    set_channel_topic: bool | None = None
    swap_on_odd_weeks: bool = False

    @classmethod
    def from_dict(cls, config: dict) -> "PagerDutyScheduleGroup":
        return cls(
            entries=[
                PagerDutyScheduleEntry.from_dict(entry) for entry in config["entries"]
            ],
            slack_group_id=config.get("slack_group_id"),
            slack_space=config.get("slack_space"),
            slack_channel_id=config.get("slack_channel_id"),
            set_channel_topic=config.get("set_channel_topic"),
            swap_on_odd_weeks=config.get("swap_on_odd_weeks", False),
        )

    def resolve_slack_config(self, default: SlackConfig) -> SlackConfig:
        """Return this group's effective Slack destination."""
        return SlackConfig(
            slack_space=self.slack_space or default.slack_space,
            slack_channel_id=self.slack_channel_id or default.slack_channel_id,
            set_channel_topic=(
                self.set_channel_topic
                if self.set_channel_topic is not None
                else default.set_channel_topic
            ),
        )


@dataclass(frozen=True)
class PagerDutyConfig:
    """PagerDuty tenant and named schedule groups."""

    tenant: str
    schedule_groups: dict[str, PagerDutyScheduleGroup]

    @classmethod
    def from_dict(cls, config: dict) -> "PagerDutyConfig":
        return cls(
            tenant=config["tenant"],
            schedule_groups={
                group_name: PagerDutyScheduleGroup.from_dict(group)
                for group_name, group in config["schedule_groups"].items()
            },
        )


@dataclass(frozen=True)
class ScheduleConfig:
    """Validated Emberpost schedule configuration."""

    id: str
    schedule: Frequency
    pagerduty: PagerDutyConfig
    slack: SlackConfig
    suspended: bool = False
    message_header: str | None = None
    message_footer: str | None = None

    @classmethod
    def from_dict(cls, config: dict) -> "ScheduleConfig":
        return cls(
            id=config["id"],
            schedule=Frequency(config["schedule"]),
            suspended=config.get("suspended", False),
            pagerduty=PagerDutyConfig.from_dict(config["pagerduty"]),
            slack=SlackConfig.from_dict(config["slack"]),
            message_header=config.get("message_header"),
            message_footer=config.get("message_footer"),
        )


def load_schedule(path: Path) -> ScheduleConfig:
    """Load and validate a schedule configuration from YAML."""
    with path.open(encoding="utf-8") as schedule_file:
        raw_config = yaml.safe_load(schedule_file)

    validate_schedule_schema(raw_config)
    return ScheduleConfig.from_dict(raw_config)


def validate_schedule_schema(config: object) -> None:
    """Validate an object against Emberpost's packaged JSON schema."""
    jsonschema.validate(config, _load_schedule_schema())


@lru_cache(maxsize=1)
def _load_schedule_schema() -> dict:
    """Load and cache Emberpost's packaged schedule schema."""
    return json.loads(
        files("emberpost.schemas").joinpath(SCHEMA_FILE).read_text(encoding="utf-8")
    )
