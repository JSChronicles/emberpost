import json
from pathlib import Path

import jsonschema
import pytest
import yaml

from emberpost.schedule_config import (
    ScheduleConfig,
    load_schedule,
    validate_schedule_schema,
)


def schedule_paths() -> list[Path]:
    return sorted([*Path("schedules").glob("*.yaml"), *Path("examples").glob("*.yaml")])


def test_load_schedule_file() -> None:
    config = load_schedule(Path("schedules/oncall.yaml"))

    assert config.id == "oncall"
    assert config.schedule == "weekly"
    assert len(config.pagerduty.schedule_groups["Platform Coverage"].entries) == 2


def test_load_example_schedule_files() -> None:
    for schedule_path in Path("examples").glob("*.yaml"):
        load_schedule(schedule_path)


def test_schedule_files_match_json_schema() -> None:
    schema = json.loads(Path("schemas/schedule.schema.json").read_text())

    for schedule_path in schedule_paths():
        config = yaml.safe_load(schedule_path.read_text())
        jsonschema.validate(config, schema)


def test_json_schema_rejects_empty_schedule_group() -> None:
    schema = json.loads(Path("schemas/schedule.schema.json").read_text())

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {
                "id": "empty-group",
                "schedule": "weekly",
                "pagerduty": {
                    "tenant": "example.pagerduty.com",
                    "schedule_groups": {"EMPTY": {"entries": []}},
                },
                "slack": {
                    "slack_space": "example.slack.com",
                    "slack_channel_id": "C123",
                },
            },
            schema,
        )


def test_json_schema_rejects_swap_on_odd_weeks_without_exactly_two_entries() -> None:
    schema = json.loads(Path("schemas/schedule.schema.json").read_text())

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(
            {
                "id": "bad-swap",
                "schedule": "weekly",
                "pagerduty": {
                    "tenant": "example.pagerduty.com",
                    "schedule_groups": {
                        "TEAM": {
                            "swap_on_odd_weeks": True,
                            "entries": [
                                {"schedule_id": "P1", "label": "First"},
                                {"schedule_id": "P2", "label": "Second"},
                                {"schedule_id": "P3", "label": "Third"},
                            ],
                        }
                    },
                },
                "slack": {
                    "slack_space": "example.slack.com",
                    "slack_channel_id": "C123",
                },
            },
            schema,
        )


def test_runtime_schema_validation_rejects_empty_schedule_group() -> None:
    with pytest.raises(jsonschema.ValidationError):
        validate_schedule_schema(
            {
                "id": "empty-group",
                "schedule": "weekly",
                "pagerduty": {
                    "tenant": "example.pagerduty.com",
                    "schedule_groups": {"EMPTY": {"entries": []}},
                },
                "slack": {
                    "slack_space": "example.slack.com",
                    "slack_channel_id": "C123",
                },
            }
        )


def test_schedule_supports_many_goalies() -> None:
    config = ScheduleConfig.from_dict(
        {
            "id": "many-goalies",
            "schedule": "weekly",
            "pagerduty": {
                "tenant": "example.pagerduty.com",
                "schedule_groups": {
                    "TEAM": {
                        "entries": [
                            {"schedule_id": f"P{i}", "label": f"Goalie {i}"}
                            for i in range(10)
                        ]
                    }
                },
            },
            "slack": {"slack_space": "example.slack.com", "slack_channel_id": "C123"},
        }
    )

    assert len(config.pagerduty.schedule_groups["TEAM"].entries) == 10


def test_schedule_group_supports_slack_group_id() -> None:
    config = ScheduleConfig.from_dict(
        {
            "id": "group-sync",
            "schedule": "weekly",
            "pagerduty": {
                "tenant": "example.pagerduty.com",
                "schedule_groups": {
                    "TEAM": {
                        "slack_group_id": "S123",
                        "entries": [
                            {"schedule_id": "P1", "label": "Primary"},
                            {"schedule_id": "P2", "label": "Secondary"},
                        ],
                    }
                },
            },
            "slack": {"slack_space": "example.slack.com", "slack_channel_id": "C123"},
        }
    )

    group = config.pagerduty.schedule_groups["TEAM"]
    assert group.slack_group_id == "S123"
    assert [entry.label for entry in group.entries] == ["Primary", "Secondary"]


def test_schedule_group_supports_swap_on_odd_weeks() -> None:
    config = ScheduleConfig.from_dict(
        {
            "id": "group-swap",
            "schedule": "weekly",
            "pagerduty": {
                "tenant": "example.pagerduty.com",
                "schedule_groups": {
                    "TEAM": {
                        "swap_on_odd_weeks": True,
                        "entries": [
                            {"schedule_id": "P1", "label": "Primary"},
                            {"schedule_id": "P2", "label": "Secondary"},
                        ],
                    }
                },
            },
            "slack": {"slack_space": "example.slack.com", "slack_channel_id": "C123"},
        }
    )

    assert config.pagerduty.schedule_groups["TEAM"].swap_on_odd_weeks is True
