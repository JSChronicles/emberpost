from pathlib import Path

import pytest

from emberpost.post import dispatch, dispatch_schedule_files
from emberpost.schedule_config import Frequency, ScheduleConfig
from tests.support import FakePagerDutyClient, FakeSlackClient, minimal_config


def test_dispatch_schedule_files_processes_multiple_files(monkeypatch) -> None:
    schedule_files = [Path("one.yaml"), Path("two.yaml")]
    dispatched: list[str] = []

    def fake_load_schedule(schedule_file: Path) -> ScheduleConfig:
        return minimal_config(schedule_file.stem)

    def fake_dispatch(
        config: ScheduleConfig, frequency: Frequency, *, dry_run: bool
    ) -> None:
        dispatched.append(f"{config.id}:{frequency}:{dry_run}")

    monkeypatch.setattr("emberpost.post.load_schedule", fake_load_schedule)
    monkeypatch.setattr("emberpost.post.dispatch", fake_dispatch)

    dispatch_schedule_files(schedule_files, Frequency.weekly, dry_run=True)

    assert dispatched == ["one:weekly:True", "two:weekly:True"]


def test_dispatch_schedule_files_continues_after_failure(monkeypatch) -> None:
    schedule_files = [Path("one.yaml"), Path("two.yaml")]
    dispatched: list[str] = []

    def fake_load_schedule(schedule_file: Path) -> ScheduleConfig:
        return minimal_config(schedule_file.stem)

    def fake_dispatch(
        config: ScheduleConfig, frequency: Frequency, *, dry_run: bool
    ) -> None:
        dispatched.append(config.id)
        if config.id == "one":
            raise ValueError("boom")

    monkeypatch.setattr("emberpost.post.load_schedule", fake_load_schedule)
    monkeypatch.setattr("emberpost.post.dispatch", fake_dispatch)

    with pytest.raises(RuntimeError, match="One or more schedule files failed"):
        dispatch_schedule_files(schedule_files, Frequency.weekly, dry_run=False)

    assert dispatched == ["one", "two"]


def test_dispatch_skips_mismatched_frequency(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs) -> None:
        raise AssertionError("client should not be created")

    monkeypatch.setattr("emberpost.post.PagerDutyClient", fail_if_called)
    monkeypatch.setattr("emberpost.post.SlackClient", fail_if_called)
    config = ScheduleConfig.from_dict(
        {
            "id": "test",
            "schedule": "daily",
            "pagerduty": {
                "tenant": "example.pagerduty.com",
                "schedule_groups": {
                    "TEAM": {"entries": [{"schedule_id": "P1", "label": "First"}]}
                },
            },
            "slack": {"slack_space": "example.slack.com", "slack_channel_id": "C123"},
        }
    )

    dispatch(config, frequency=Frequency.weekly, dry_run=True)


def test_dispatch_topic_without_user_group_skips_slack_user_lookup(monkeypatch) -> None:
    pagerduty_client = FakePagerDutyClient()
    slack_client = FakeSlackClient()
    monkeypatch.setattr(
        "emberpost.post.PagerDutyClient", lambda tenant: pagerduty_client
    )
    monkeypatch.setattr("emberpost.post.SlackClient", lambda slack_space: slack_client)
    config = ScheduleConfig.from_dict(
        {
            "id": "test",
            "schedule": "weekly",
            "pagerduty": {
                "tenant": "example.pagerduty.com",
                "schedule_groups": {
                    "TEAM": {
                        "entries": [
                            {"schedule_id": "P1", "label": "First"},
                            {"schedule_id": "P2", "label": "Second"},
                        ]
                    }
                },
            },
            "slack": {
                "slack_space": "example.slack.com",
                "slack_channel_id": "C123",
                "set_channel_topic": True,
            },
        }
    )

    dispatch(config, frequency=Frequency.weekly, dry_run=False)

    assert slack_client.requested_emails == []
    assert slack_client.topics == ["TEAM\nFirst: One User\nSecond: Two User"]


def test_dispatch_topic_with_user_group_still_resolves_slack_users(monkeypatch) -> None:
    pagerduty_client = FakePagerDutyClient()
    slack_client = FakeSlackClient()
    monkeypatch.setattr(
        "emberpost.post.PagerDutyClient", lambda tenant: pagerduty_client
    )
    monkeypatch.setattr("emberpost.post.SlackClient", lambda slack_space: slack_client)
    config = ScheduleConfig.from_dict(
        {
            "id": "test",
            "schedule": "weekly",
            "pagerduty": {
                "tenant": "example.pagerduty.com",
                "schedule_groups": {
                    "TEAM": {
                        "slack_group_id": "S123",
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
                "set_channel_topic": True,
            },
        }
    )

    dispatch(config, frequency=Frequency.weekly, dry_run=False)

    assert slack_client.requested_emails == ["one@example.com", "two@example.com"]
    assert slack_client.user_group_updates == [("S123", ["U1", "U2"])]


def test_dispatch_updates_each_group_user_group(monkeypatch) -> None:
    pagerduty_client = FakePagerDutyClient()
    slack_client = FakeSlackClient()
    monkeypatch.setattr(
        "emberpost.post.PagerDutyClient", lambda tenant: pagerduty_client
    )
    monkeypatch.setattr("emberpost.post.SlackClient", lambda slack_space: slack_client)
    config = ScheduleConfig.from_dict(
        {
            "id": "test",
            "schedule": "weekly",
            "pagerduty": {
                "tenant": "example.pagerduty.com",
                "schedule_groups": {
                    "PLATFORM": {
                        "slack_group_id": "S123",
                        "entries": [
                            {"schedule_id": "P1", "label": "First"},
                            {"schedule_id": "P2", "label": "Second"},
                        ],
                    },
                    "DATABASE": {
                        "slack_group_id": "S456",
                        "entries": [{"schedule_id": "P3", "label": "Third"}],
                    },
                },
            },
            "slack": {
                "slack_space": "example.slack.com",
                "slack_channel_id": "C123",
                "set_channel_topic": True,
            },
        }
    )

    dispatch(config, frequency=Frequency.weekly, dry_run=False)

    assert slack_client.user_group_updates == [("S123", ["U1", "U2"]), ("S456", ["U1"])]


def test_dispatch_routes_groups_to_their_effective_slack_destinations(
    monkeypatch,
) -> None:
    pagerduty_client = FakePagerDutyClient()
    slack_clients: dict[str, FakeSlackClient] = {}
    created_workspaces: list[str] = []

    def fake_slack_client(slack_space: str) -> FakeSlackClient:
        client = FakeSlackClient()
        created_workspaces.append(slack_space)
        slack_clients[slack_space] = client
        return client

    monkeypatch.setattr(
        "emberpost.post.PagerDutyClient", lambda tenant: pagerduty_client
    )
    monkeypatch.setattr("emberpost.post.SlackClient", fake_slack_client)
    config = ScheduleConfig.from_dict(
        {
            "id": "multi-destination",
            "schedule": "weekly",
            "pagerduty": {
                "tenant": "example.pagerduty.com",
                "schedule_groups": {
                    "PLATFORM": {
                        "entries": [{"schedule_id": "P1", "label": "Primary"}]
                    },
                    "DATABASE": {
                        "slack_space": "database.slack.com",
                        "slack_channel_id": "C456",
                        "set_channel_topic": False,
                        "entries": [{"schedule_id": "P2", "label": "Secondary"}],
                    },
                },
            },
            "slack": {
                "slack_space": "example.slack.com",
                "slack_channel_id": "C123",
                "set_channel_topic": True,
            },
        }
    )

    dispatch(config, frequency=Frequency.weekly, dry_run=False)

    assert created_workspaces == ["database.slack.com", "example.slack.com"]
    default_client = slack_clients["example.slack.com"]
    database_client = slack_clients["database.slack.com"]
    assert default_client.topics == ["PLATFORM\nPrimary: One User"]
    assert default_client.topic_channels == ["C123"]
    assert default_client.messages == []
    assert default_client.requested_emails == []
    assert database_client.messages == ["DATABASE\nSecondary: <@U2>"]
    assert database_client.message_channels == ["C456"]
    assert database_client.topics == []
    assert database_client.requested_emails == ["two@example.com"]


def test_dispatch_reuses_slack_client_across_channels_in_same_workspace(
    monkeypatch,
) -> None:
    pagerduty_client = FakePagerDutyClient()
    slack_client = FakeSlackClient()
    created_workspaces: list[str] = []

    def fake_slack_client(slack_space: str) -> FakeSlackClient:
        created_workspaces.append(slack_space)
        return slack_client

    monkeypatch.setattr(
        "emberpost.post.PagerDutyClient", lambda tenant: pagerduty_client
    )
    monkeypatch.setattr("emberpost.post.SlackClient", fake_slack_client)
    config = ScheduleConfig.from_dict(
        {
            "id": "same-workspace",
            "schedule": "weekly",
            "pagerduty": {
                "tenant": "example.pagerduty.com",
                "schedule_groups": {
                    "PLATFORM": {
                        "entries": [{"schedule_id": "P1", "label": "Primary"}]
                    },
                    "DATABASE": {
                        "slack_channel_id": "C456",
                        "entries": [{"schedule_id": "P2", "label": "Secondary"}],
                    },
                },
            },
            "slack": {"slack_space": "example.slack.com", "slack_channel_id": "C123"},
        }
    )

    dispatch(config, frequency=Frequency.weekly, dry_run=False)

    assert created_workspaces == ["example.slack.com"]
    assert slack_client.message_channels == ["C123", "C456"]
    assert slack_client.messages == [
        "PLATFORM\nPrimary: <@U1>",
        "DATABASE\nSecondary: <@U2>",
    ]


def test_multi_destination_dry_run_reports_without_writing(monkeypatch, capsys) -> None:
    pagerduty_client = FakePagerDutyClient()
    slack_clients: dict[str, FakeSlackClient] = {}

    def fake_slack_client(slack_space: str) -> FakeSlackClient:
        client = FakeSlackClient()
        slack_clients[slack_space] = client
        return client

    monkeypatch.setattr(
        "emberpost.post.PagerDutyClient", lambda tenant: pagerduty_client
    )
    monkeypatch.setattr("emberpost.post.SlackClient", fake_slack_client)
    config = ScheduleConfig.from_dict(
        {
            "id": "dry-run-destinations",
            "schedule": "weekly",
            "pagerduty": {
                "tenant": "example.pagerduty.com",
                "schedule_groups": {
                    "PLATFORM": {
                        "slack_group_id": "S123",
                        "entries": [{"schedule_id": "P1", "label": "Primary"}],
                    },
                    "DATABASE": {
                        "slack_space": "database.slack.com",
                        "slack_channel_id": "C456",
                        "set_channel_topic": False,
                        "entries": [{"schedule_id": "P2", "label": "Secondary"}],
                    },
                },
            },
            "slack": {
                "slack_space": "example.slack.com",
                "slack_channel_id": "C123",
                "set_channel_topic": True,
            },
        }
    )

    dispatch(config, frequency=Frequency.weekly, dry_run=True)

    output = capsys.readouterr().out
    assert "Slack channel topic for C123 in example.slack.com" in output
    assert "Slack user group S123 in example.slack.com: U1" in output
    assert "Slack channel message for C456 in database.slack.com" in output
    assert "PLATFORM\nPrimary: One User" in output
    assert "DATABASE\nSecondary: <@U2>" in output
    for slack_client in slack_clients.values():
        assert slack_client.messages == []
        assert slack_client.topics == []
        assert slack_client.user_group_updates == []
