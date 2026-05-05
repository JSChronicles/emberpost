import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import jsonschema
import yaml


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "schedule.schema.json"


class Frequency(StrEnum):
    daily = "daily"
    weekly = "weekly"
    manual = "manual"


@dataclass(frozen=True)
class PagerDutyScheduleEntry:
    schedule_id: str
    label: str

    @classmethod
    def from_dict(cls, config: dict) -> "PagerDutyScheduleEntry":
        return cls(schedule_id=config["schedule_id"], label=config["label"])


@dataclass(frozen=True)
class PagerDutyScheduleGroup:
    entries: list[PagerDutyScheduleEntry]
    slack_group_id: str | None = None
    swap_on_odd_weeks: bool = False

    @classmethod
    def from_dict(cls, config: dict) -> "PagerDutyScheduleGroup":
        return cls(
            entries=[
                PagerDutyScheduleEntry.from_dict(entry) for entry in config["entries"]
            ],
            slack_group_id=config.get("slack_group_id"),
            swap_on_odd_weeks=config.get("swap_on_odd_weeks", False),
        )


@dataclass(frozen=True)
class PagerDutyConfig:
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
class SlackConfig:
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
class ScheduleConfig:
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
    with path.open(encoding="utf-8") as schedule_file:
        raw_config = yaml.safe_load(schedule_file)

    validate_schedule_schema(raw_config)
    return ScheduleConfig.from_dict(raw_config)


def validate_schedule_schema(config: object) -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.validate(config, schema)
