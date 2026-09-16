from datetime import date

from emberpost.post import collect_assignments, render
from emberpost.schedule_config import ScheduleConfig
from tests.support import FakePagerDutyClient, msteams_destination, slack_destination


def test_collect_assignments_batches_pagerduty_without_provider_lookups() -> None:
    config = ScheduleConfig.from_dict(
        {
            "id": "test",
            "schedule": "weekly",
            "destination": slack_destination(),
            "pagerduty_tenant": "example.pagerduty.com",
            "schedule_groups": {
                "TEAM": {
                    "entries": [
                        {"schedule_id": "P1", "label": "First"},
                        {"schedule_id": "P2", "label": "Second"},
                        {"schedule_id": "P3", "label": "Third"},
                    ]
                }
            },
        }
    )
    pagerduty_client = FakePagerDutyClient()

    assignments = collect_assignments(config, pagerduty_client)

    assert pagerduty_client.requested_schedule_ids == [["P1", "P2", "P3"]]
    assert [assignment.email for assignment in assignments] == [
        "one@example.com",
        "two@example.com",
        "one@example.com",
    ]
    assert (
        render(assignments)
        == "TEAM\nFirst: One User\nSecond: Two User\nThird: One User"
    )


def test_collect_assignments_applies_group_destination_override() -> None:
    config = ScheduleConfig.from_dict(
        {
            "id": "test",
            "schedule": "weekly",
            "destination": slack_destination(),
            "pagerduty_tenant": "example.pagerduty.com",
            "schedule_groups": {
                "SLACK": {"entries": [{"schedule_id": "P1", "label": "First"}]},
                "TEAMS": {
                    "destination": msteams_destination(),
                    "entries": [{"schedule_id": "P2", "label": "Second"}],
                },
            },
        }
    )

    assignments = collect_assignments(config, FakePagerDutyClient())

    assert assignments[0].destination == config.destination
    assert assignments[1].destination == config.schedule_groups["TEAMS"].destination


def test_render_uses_provider_identities_when_supplied() -> None:
    config = ScheduleConfig.from_dict(
        {
            "id": "test",
            "schedule": "weekly",
            "destination": slack_destination(),
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
    assignments = collect_assignments(config, FakePagerDutyClient())

    assert (
        render(assignments, {"one@example.com": "<@U1>", "two@example.com": "<@U2>"})
        == "TEAM\nFirst: <@U1>\nSecond: <@U2>"
    )


def test_collect_assignments_swaps_entries_only_on_odd_weeks() -> None:
    config = ScheduleConfig.from_dict(
        {
            "id": "test",
            "schedule": "weekly",
            "destination": slack_destination(),
            "pagerduty_tenant": "example.pagerduty.com",
            "schedule_groups": {
                "TEAM": {
                    "swap_on_odd_weeks": True,
                    "entries": [
                        {"schedule_id": "P1", "label": "First"},
                        {"schedule_id": "P2", "label": "Second"},
                    ],
                }
            },
        }
    )

    odd_assignments = collect_assignments(
        config, FakePagerDutyClient(), today=date.fromisocalendar(2026, 1, 1)
    )
    even_assignments = collect_assignments(
        config, FakePagerDutyClient(), today=date.fromisocalendar(2026, 2, 1)
    )

    assert [assignment.schedule.schedule_id for assignment in odd_assignments] == [
        "P2",
        "P1",
    ]
    assert [assignment.schedule.schedule_id for assignment in even_assignments] == [
        "P1",
        "P2",
    ]
