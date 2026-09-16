from pathlib import Path

import jsonschema
import pytest
import yaml

from emberpost.schedule_config import (
    DestinationProviderName,
    MSTeamsProviderOptions,
    ScheduleConfig,
    SlackProviderOptions,
    _load_schedule_schema,
    load_schedule,
    validate_schedule_schema,
)
from tests.support import msteams_destination, slack_destination


def schedule_paths() -> list[Path]:
    """Return checked-in schedule and example YAML paths."""
    return sorted([*Path("schedules").glob("*.yaml"), *Path("examples").glob("*.yaml")])


def schedule_dict(*, destination: dict[str, object] | None = None) -> dict:
    """Return a minimal schedule configuration dictionary."""
    return {
        "id": "test",
        "schedule": "weekly",
        "destination": destination or slack_destination(),
        "pagerduty_tenant": "example.pagerduty.com",
        "schedule_groups": {
            "TEAM": {"entries": [{"schedule_id": "P1", "label": "Primary"}]}
        },
    }


def test_load_schedule_file() -> None:
    config = load_schedule(Path("schedules/oncall.yaml"))

    assert config.id == "oncall"
    assert config.schedule == "weekly"
    assert len(config.schedule_groups["Platform Coverage"].entries) == 2


def test_load_example_schedule_files() -> None:
    for schedule_path in Path("examples").glob("*.yaml"):
        load_schedule(schedule_path)


def test_schedule_files_match_json_schema() -> None:
    schema = _load_schedule_schema()

    for schedule_path in schedule_paths():
        config = yaml.safe_load(schedule_path.read_text())
        jsonschema.validate(config, schema)


def test_json_schema_rejects_empty_schedule_group() -> None:
    config = schedule_dict()
    config["schedule_groups"]["TEAM"]["entries"] = []

    with pytest.raises(jsonschema.ValidationError):
        validate_schedule_schema(config)


def test_json_schema_rejects_swap_without_exactly_two_entries() -> None:
    config = schedule_dict()
    config["schedule_groups"]["TEAM"].update(
        {
            "swap_on_odd_weeks": True,
            "entries": [
                {"schedule_id": "P1", "label": "First"},
                {"schedule_id": "P2", "label": "Second"},
                {"schedule_id": "P3", "label": "Third"},
            ],
        }
    )

    with pytest.raises(jsonschema.ValidationError):
        validate_schedule_schema(config)


def test_json_schema_rejects_legacy_slack_configuration() -> None:
    config = schedule_dict()
    config["slack"] = {"slack_space": "example.slack.com", "slack_channel_id": "C123"}
    del config["destination"]

    with pytest.raises(jsonschema.ValidationError):
        validate_schedule_schema(config)


def test_json_schema_rejects_provider_options_for_another_provider() -> None:
    config = schedule_dict(
        destination={
            "provider": {
                "name": "msteams",
                "options": {"space": "example.slack.com", "channel_id": "C123"},
            }
        }
    )

    with pytest.raises(jsonschema.ValidationError):
        validate_schedule_schema(config)


def test_schedule_schema_is_cached() -> None:
    assert _load_schedule_schema() is _load_schedule_schema()


def test_schedule_parses_slack_provider_options() -> None:
    config = ScheduleConfig.from_dict(schedule_dict())

    assert config.destination.provider.name is DestinationProviderName.slack
    assert config.destination.provider.options == SlackProviderOptions(
        space="example.slack.com", channel_id="C123", set_channel_topic=False
    )


def test_schedule_parses_msteams_provider_options() -> None:
    config = ScheduleConfig.from_dict(
        schedule_dict(destination=msteams_destination("MSTEAMS_WEBHOOK_ONCALL"))
    )

    assert config.destination.provider.name is DestinationProviderName.msteams
    assert config.destination.provider.options == MSTeamsProviderOptions(
        webhook_env="MSTEAMS_WEBHOOK_ONCALL"
    )


def test_schedule_group_inherits_default_destination() -> None:
    config = ScheduleConfig.from_dict(schedule_dict())
    group = config.schedule_groups["TEAM"]

    assert group.resolve_destination(config.destination) == config.destination


def test_schedule_group_completely_overrides_default_destination() -> None:
    raw_config = schedule_dict()
    raw_config["schedule_groups"]["TEAM"]["destination"] = msteams_destination(
        "MSTEAMS_WEBHOOK_TEAM"
    )

    config = ScheduleConfig.from_dict(raw_config)
    destination = config.schedule_groups["TEAM"].resolve_destination(config.destination)

    assert destination.provider.name is DestinationProviderName.msteams
    assert destination.provider.options == MSTeamsProviderOptions(
        webhook_env="MSTEAMS_WEBHOOK_TEAM"
    )


def test_schedule_group_can_override_msteams_default_with_slack() -> None:
    raw_config = schedule_dict(destination=msteams_destination())
    raw_config["schedule_groups"]["TEAM"].update(
        {"destination": slack_destination(), "slack_group_id": "S123"}
    )

    config = ScheduleConfig.from_dict(raw_config)
    destination = config.schedule_groups["TEAM"].resolve_destination(config.destination)

    assert destination.provider.name is DestinationProviderName.slack


def test_schedule_rejects_slack_group_for_msteams_destination() -> None:
    raw_config = schedule_dict(destination=msteams_destination())
    raw_config["schedule_groups"]["TEAM"]["slack_group_id"] = "S123"

    with pytest.raises(ValueError, match="effective destination provider is not slack"):
        ScheduleConfig.from_dict(raw_config)
