from pathlib import Path

import pytest

from emberpost.post import dispatch, dispatch_schedule_files
from emberpost.schedule_config import Frequency, ScheduleConfig
from tests.support import (
    FakeMSTeamsClient,
    FakePagerDutyClient,
    FakeSlackClient,
    minimal_config,
    msteams_destination,
    slack_destination,
)


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


def test_dispatch_skips_mismatched_frequency_before_creating_clients(
    monkeypatch,
) -> None:
    def fail_if_called(*args, **kwargs) -> None:
        raise AssertionError("client should not be created")

    monkeypatch.setattr("emberpost.post.PagerDutyClient", fail_if_called)
    monkeypatch.setattr("emberpost.post.SlackClient", fail_if_called)
    monkeypatch.setattr("emberpost.post.MSTeamsClient", fail_if_called)
    config = minimal_config()

    dispatch(config, frequency=Frequency.daily, dry_run=True)


def test_dispatch_slack_topic_uses_names_without_user_lookup(monkeypatch) -> None:
    pagerduty_client = FakePagerDutyClient()
    slack_client = FakeSlackClient()
    monkeypatch.setattr(
        "emberpost.post.PagerDutyClient", lambda tenant: pagerduty_client
    )
    monkeypatch.setattr("emberpost.post.SlackClient", lambda space: slack_client)
    config = ScheduleConfig.from_dict(
        {
            "id": "topic",
            "schedule": "weekly",
            "destination": slack_destination(set_channel_topic=True),
            "pagerduty_tenant": "example.pagerduty.com",
            "schedule_groups": {
                "TEAM": {
                    "entries": [
                        {"schedule_id": "P1", "label": "First"},
                        {"schedule_id": "P2", "label": "Second"},
                    ]
                }
            },
        }
    )

    dispatch(config, frequency=Frequency.weekly, dry_run=False)

    assert slack_client.requested_emails == []
    assert slack_client.topic_channels == ["C123"]
    assert slack_client.topics == ["TEAM\nFirst: One User\nSecond: Two User"]


def test_dispatch_slack_message_and_user_group_resolve_users_once(monkeypatch) -> None:
    pagerduty_client = FakePagerDutyClient()
    slack_client = FakeSlackClient()
    monkeypatch.setattr(
        "emberpost.post.PagerDutyClient", lambda tenant: pagerduty_client
    )
    monkeypatch.setattr("emberpost.post.SlackClient", lambda space: slack_client)
    config = ScheduleConfig.from_dict(
        {
            "id": "message",
            "schedule": "weekly",
            "destination": slack_destination(),
            "pagerduty_tenant": "example.pagerduty.com",
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
        }
    )

    dispatch(config, frequency=Frequency.weekly, dry_run=False)

    assert slack_client.requested_emails == ["one@example.com", "two@example.com"]
    assert slack_client.messages == ["TEAM\nFirst: <@U1>\nSecond: <@U2>\nThird: <@U1>"]
    assert slack_client.user_group_updates == [("S123", ["U1", "U2"])]


def test_dispatch_routes_groups_to_slack_and_msteams(monkeypatch) -> None:
    pagerduty_client = FakePagerDutyClient()
    slack_client = FakeSlackClient()
    teams_clients: list[FakeMSTeamsClient] = []

    def fake_teams_client(webhook_env: str) -> FakeMSTeamsClient:
        client = FakeMSTeamsClient(webhook_env)
        teams_clients.append(client)
        return client

    monkeypatch.setattr(
        "emberpost.post.PagerDutyClient", lambda tenant: pagerduty_client
    )
    monkeypatch.setattr("emberpost.post.SlackClient", lambda space: slack_client)
    monkeypatch.setattr("emberpost.post.MSTeamsClient", fake_teams_client)
    config = ScheduleConfig.from_dict(
        {
            "id": "mixed",
            "schedule": "weekly",
            "message_header": "Current rotation",
            "message_footer": "Escalate in PagerDuty",
            "destination": slack_destination(),
            "pagerduty_tenant": "example.pagerduty.com",
            "schedule_groups": {
                "PLATFORM": {"entries": [{"schedule_id": "P1", "label": "Primary"}]},
                "INCIDENT": {
                    "destination": msteams_destination("MSTEAMS_WEBHOOK_INCIDENT"),
                    "entries": [{"schedule_id": "P2", "label": "Commander"}],
                },
            },
        }
    )

    dispatch(config, frequency=Frequency.weekly, dry_run=False)

    assert slack_client.messages == [
        "Current rotation\nPLATFORM\nPrimary: <@U1>\nEscalate in PagerDuty"
    ]
    assert [client.webhook_env for client in teams_clients] == [
        "MSTEAMS_WEBHOOK_INCIDENT"
    ]
    assert teams_clients[0].messages == [
        "Current rotation\nINCIDENT\nCommander: Two User\nEscalate in PagerDuty"
    ]


def test_dispatch_reuses_slack_client_and_user_cache_across_destinations(
    monkeypatch,
) -> None:
    pagerduty_client = FakePagerDutyClient()
    slack_client = FakeSlackClient()
    created_spaces: list[str] = []

    def fake_slack_client(space: str) -> FakeSlackClient:
        created_spaces.append(space)
        return slack_client

    monkeypatch.setattr(
        "emberpost.post.PagerDutyClient", lambda tenant: pagerduty_client
    )
    monkeypatch.setattr("emberpost.post.SlackClient", fake_slack_client)
    config = ScheduleConfig.from_dict(
        {
            "id": "same-workspace",
            "schedule": "weekly",
            "destination": slack_destination(channel_id="C123"),
            "pagerduty_tenant": "example.pagerduty.com",
            "schedule_groups": {
                "PLATFORM": {"entries": [{"schedule_id": "P1", "label": "Primary"}]},
                "DATABASE": {
                    "destination": slack_destination(channel_id="C456"),
                    "entries": [{"schedule_id": "P3", "label": "Secondary"}],
                },
            },
        }
    )

    dispatch(config, frequency=Frequency.weekly, dry_run=False)

    assert created_spaces == ["example.slack.com"]
    assert slack_client.requested_emails == ["one@example.com"]
    assert slack_client.message_channels == ["C123", "C456"]


def test_mixed_destination_dry_run_does_not_write(monkeypatch, capsys) -> None:
    pagerduty_client = FakePagerDutyClient()
    slack_client = FakeSlackClient()
    teams_clients: list[FakeMSTeamsClient] = []

    def fake_teams_client(webhook_env: str) -> FakeMSTeamsClient:
        client = FakeMSTeamsClient(webhook_env)
        teams_clients.append(client)
        return client

    monkeypatch.setattr(
        "emberpost.post.PagerDutyClient", lambda tenant: pagerduty_client
    )
    monkeypatch.setattr("emberpost.post.SlackClient", lambda space: slack_client)
    monkeypatch.setattr("emberpost.post.MSTeamsClient", fake_teams_client)
    config = ScheduleConfig.from_dict(
        {
            "id": "dry-run",
            "schedule": "weekly",
            "destination": slack_destination(),
            "pagerduty_tenant": "example.pagerduty.com",
            "schedule_groups": {
                "PLATFORM": {"entries": [{"schedule_id": "P1", "label": "Primary"}]},
                "INCIDENT": {
                    "destination": msteams_destination(),
                    "entries": [{"schedule_id": "P2", "label": "Commander"}],
                },
            },
        }
    )

    dispatch(config, frequency=Frequency.weekly, dry_run=True)

    output = capsys.readouterr().out
    assert "Slack channel message for C123 in example.slack.com" in output
    assert "Microsoft Teams message using MSTEAMS_WEBHOOK_TEST" in output
    assert "Commander: Two User" in output
    assert slack_client.messages == []
    assert slack_client.topics == []
    assert slack_client.user_group_updates == []
    assert len(teams_clients) == 1
    assert teams_clients[0].messages == []
