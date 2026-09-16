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


class DestinationProviderName(StrEnum):
    """Supported notification destination providers."""

    slack = "slack"
    msteams = "msteams"


@dataclass(frozen=True)
class PagerDutyScheduleEntry:
    """One labeled PagerDuty schedule to resolve."""

    schedule_id: str
    label: str

    @classmethod
    def from_dict(cls, config: dict) -> "PagerDutyScheduleEntry":
        """Create a schedule entry from validated configuration."""
        return cls(schedule_id=config["schedule_id"], label=config["label"])


@dataclass(frozen=True)
class SlackProviderOptions:
    """Slack workspace, channel, and delivery mode."""

    space: str
    channel_id: str
    set_channel_topic: bool = False

    @classmethod
    def from_dict(cls, config: dict) -> "SlackProviderOptions":
        """Create Slack provider options from validated configuration."""
        return cls(
            space=config["space"],
            channel_id=config["channel_id"],
            set_channel_topic=config.get("set_channel_topic", False),
        )


@dataclass(frozen=True)
class MSTeamsProviderOptions:
    """Microsoft Teams Workflows webhook configuration."""

    webhook_env: str

    @classmethod
    def from_dict(cls, config: dict) -> "MSTeamsProviderOptions":
        """Create Teams provider options from validated configuration."""
        return cls(webhook_env=config["webhook_env"])


DestinationProviderOptions = SlackProviderOptions | MSTeamsProviderOptions


@dataclass(frozen=True)
class DestinationProvider:
    """Named provider and its provider-specific options."""

    name: DestinationProviderName
    options: DestinationProviderOptions

    @classmethod
    def from_dict(cls, config: dict) -> "DestinationProvider":
        """Create a destination provider from validated configuration."""
        name = DestinationProviderName(config["name"])
        if name is DestinationProviderName.slack:
            options: DestinationProviderOptions = SlackProviderOptions.from_dict(
                config["options"]
            )
        else:
            options = MSTeamsProviderOptions.from_dict(config["options"])
        return cls(name=name, options=options)


@dataclass(frozen=True)
class Destination:
    """Notification destination for one or more schedule groups."""

    provider: DestinationProvider

    @classmethod
    def from_dict(cls, config: dict) -> "Destination":
        """Create a destination from validated configuration."""
        return cls(provider=DestinationProvider.from_dict(config["provider"]))


@dataclass(frozen=True)
class PagerDutyScheduleGroup:
    """A named schedule group with an optional destination override."""

    entries: list[PagerDutyScheduleEntry]
    destination: Destination | None = None
    slack_group_id: str | None = None
    swap_on_odd_weeks: bool = False

    @classmethod
    def from_dict(cls, config: dict) -> "PagerDutyScheduleGroup":
        """Create a schedule group from validated configuration."""
        return cls(
            entries=[
                PagerDutyScheduleEntry.from_dict(entry) for entry in config["entries"]
            ],
            destination=(
                Destination.from_dict(config["destination"])
                if "destination" in config
                else None
            ),
            slack_group_id=config.get("slack_group_id"),
            swap_on_odd_weeks=config.get("swap_on_odd_weeks", False),
        )

    def resolve_destination(self, default: Destination) -> Destination:
        """Return this group's override or the schedule default destination."""
        return self.destination or default


@dataclass(frozen=True)
class ScheduleConfig:
    """Validated Emberpost schedule configuration."""

    id: str
    schedule: Frequency
    destination: Destination
    pagerduty_tenant: str
    schedule_groups: dict[str, PagerDutyScheduleGroup]
    suspended: bool = False
    message_header: str | None = None
    message_footer: str | None = None

    @classmethod
    def from_dict(cls, config: dict) -> "ScheduleConfig":
        """Create and validate runtime configuration from a dictionary."""
        schedule_config = cls(
            id=config["id"],
            schedule=Frequency(config["schedule"]),
            destination=Destination.from_dict(config["destination"]),
            pagerduty_tenant=config["pagerduty_tenant"],
            schedule_groups={
                group_name: PagerDutyScheduleGroup.from_dict(group)
                for group_name, group in config["schedule_groups"].items()
            },
            suspended=config.get("suspended", False),
            message_header=config.get("message_header"),
            message_footer=config.get("message_footer"),
        )
        schedule_config._validate_provider_rules()
        return schedule_config

    def _validate_provider_rules(self) -> None:
        """Validate rules that depend on an inherited destination."""
        for group_name, group in self.schedule_groups.items():
            destination = group.resolve_destination(self.destination)
            if (
                group.slack_group_id is not None
                and destination.provider.name is not DestinationProviderName.slack
            ):
                raise ValueError(
                    f"Schedule group {group_name!r} sets slack_group_id but its "
                    "effective destination provider is not slack"
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
