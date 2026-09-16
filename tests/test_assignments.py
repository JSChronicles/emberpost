from datetime import date

from emberpost.post import collect_assignments, render
from emberpost.schedule_config import ScheduleConfig
from tests.support import FakePagerDutyClient, FakeSlackClient, fake_slack_clients


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

    assignments = collect_assignments(
        config, pagerduty_client, fake_slack_clients(config, slack_client)
    )

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
        config, FakePagerDutyClient(), fake_slack_clients(config, slack_client)
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
    slack_client = FakeSlackClient()
    assignments = collect_assignments(
        config, FakePagerDutyClient(), fake_slack_clients(config, slack_client)
    )

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
        fake_slack_clients(config, FakeSlackClient()),
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
        fake_slack_clients(config, FakeSlackClient()),
        today=date.fromisocalendar(2026, 2, 1),
    )

    assert [assignment.schedule.schedule_id for assignment in assignments] == [
        "P1",
        "P2",
    ]
    assert (
        render(assignments, for_topic=True) == "TEAM\nFirst: One User\nSecond: Two User"
    )
