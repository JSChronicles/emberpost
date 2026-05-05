from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pytest

from emberpost.post import (
    collect_assignments,
    dispatch,
    dispatch_schedule_files,
    render,
)
from emberpost.schedule_config import Frequency, ScheduleConfig


@dataclass(frozen=True)
class FakePagerDutyOnCall:
    email: str
    name: str


class FakePagerDutyClient:
    def __init__(self) -> None:
        self.requested_schedule_ids: list[list[str]] = []

    def get_oncalls(self, schedule_ids: list[str]) -> dict[str, FakePagerDutyOnCall]:
        self.requested_schedule_ids.append(schedule_ids)
        return {
            "P1": FakePagerDutyOnCall(email="one@example.com", name="One User"),
            "P2": FakePagerDutyOnCall(email="two@example.com", name="Two User"),
            "P3": FakePagerDutyOnCall(email="one@example.com", name="One User"),
        }


class FakeSlackClient:
    def __init__(self) -> None:
        self.requested_emails: list[str] = []
        self.messages: list[str] = []
        self.topics: list[str] = []
        self.user_group_updates: list[tuple[str, list[str]]] = []

    def get_user_id_by_email(self, email: str) -> str:
        self.requested_emails.append(email)
        return {"one@example.com": "U1", "two@example.com": "U2"}[email]

    def post_message(self, message: str) -> None:
        self.messages.append(message)

    def update_channel_topic(self, topic: str) -> None:
        self.topics.append(topic)

    def update_user_group(self, user_group_id: str, user_ids: list[str]) -> None:
        self.user_group_updates.append((user_group_id, user_ids))


def minimal_config(config_id: str = "test") -> ScheduleConfig:
    return ScheduleConfig.from_dict(
        {
            "id": config_id,
            "schedule": "weekly",
            "pagerduty": {
                "tenant": "example.pagerduty.com",
                "schedule_groups": {
                    "TEAM": {"entries": [{"schedule_id": "P1", "label": "First"}]}
                },
            },
            "slack": {"slack_space": "example.slack.com", "slack_channel_id": "C123"},
        }
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


def test_collect_assignments_batches_pagerduty_and_caches_slack_users() -> None:
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
                            {"schedule_id": "P3", "label": "Third"},
                        ]
                    }
                },
            },
            "slack": {"slack_space": "example.slack.com", "slack_channel_id": "C123"},
        }
    )
    pagerduty_client = FakePagerDutyClient()
    slack_client = FakeSlackClient()

    assignments = collect_assignments(config, pagerduty_client, slack_client)

    assert pagerduty_client.requested_schedule_ids == [["P1", "P2", "P3"]]
    assert slack_client.requested_emails == ["one@example.com", "two@example.com"]
    assert [assignment.slack_user_id for assignment in assignments] == [
        "U1",
        "U2",
        "U1",
    ]


def test_collect_assignments_can_skip_slack_user_lookup_for_topic_only() -> None:
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
    slack_client = FakeSlackClient()

    assignments = collect_assignments(
        config, FakePagerDutyClient(), slack_client, resolve_slack_users=False
    )

    assert slack_client.requested_emails == []
    assert [assignment.slack_user_id for assignment in assignments] == [None, None]
    assert (
        render(assignments, for_topic=True) == "TEAM\nFirst: One User\nSecond: Two User"
    )


def test_render_topic() -> None:
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
            "slack": {"slack_space": "example.slack.com", "slack_channel_id": "C123"},
        }
    )
    assignments = collect_assignments(config, FakePagerDutyClient(), FakeSlackClient())

    assert (
        render(assignments, for_topic=True) == "TEAM\nFirst: One User\nSecond: Two User"
    )


def test_collect_assignments_swaps_two_entries_on_odd_weeks() -> None:
    config = ScheduleConfig.from_dict(
        {
            "id": "test",
            "schedule": "weekly",
            "pagerduty": {
                "tenant": "example.pagerduty.com",
                "schedule_groups": {
                    "TEAM": {
                        "swap_on_odd_weeks": True,
                        "entries": [
                            {"schedule_id": "P1", "label": "First"},
                            {"schedule_id": "P2", "label": "Second"},
                        ],
                    }
                },
            },
            "slack": {"slack_space": "example.slack.com", "slack_channel_id": "C123"},
        }
    )

    assignments = collect_assignments(
        config,
        FakePagerDutyClient(),
        FakeSlackClient(),
        today=date.fromisocalendar(2026, 1, 1),
    )

    assert [assignment.schedule.schedule_id for assignment in assignments] == [
        "P2",
        "P1",
    ]
    assert (
        render(assignments, for_topic=True) == "TEAM\nSecond: Two User\nFirst: One User"
    )


def test_collect_assignments_keeps_two_entries_on_even_weeks() -> None:
    config = ScheduleConfig.from_dict(
        {
            "id": "test",
            "schedule": "weekly",
            "pagerduty": {
                "tenant": "example.pagerduty.com",
                "schedule_groups": {
                    "TEAM": {
                        "swap_on_odd_weeks": True,
                        "entries": [
                            {"schedule_id": "P1", "label": "First"},
                            {"schedule_id": "P2", "label": "Second"},
                        ],
                    }
                },
            },
            "slack": {"slack_space": "example.slack.com", "slack_channel_id": "C123"},
        }
    )

    assignments = collect_assignments(
        config,
        FakePagerDutyClient(),
        FakeSlackClient(),
        today=date.fromisocalendar(2026, 2, 1),
    )

    assert [assignment.schedule.schedule_id for assignment in assignments] == [
        "P1",
        "P2",
    ]
    assert (
        render(assignments, for_topic=True) == "TEAM\nFirst: One User\nSecond: Two User"
    )


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
    monkeypatch.setattr(
        "emberpost.post.SlackClient", lambda slack_space, channel_id: slack_client
    )
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
    monkeypatch.setattr(
        "emberpost.post.SlackClient", lambda slack_space, channel_id: slack_client
    )
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
    monkeypatch.setattr(
        "emberpost.post.SlackClient", lambda slack_space, channel_id: slack_client
    )
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
