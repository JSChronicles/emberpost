import pytest

from emberpost.pagerduty import PagerDutyClient
from emberpost.slack import SlackClient


def test_pagerduty_client_missing_api_key_names_tenant(monkeypatch) -> None:
    monkeypatch.delenv("PAGERDUTY_API_KEY_EXAMPLE_PAGERDUTY_COM", raising=False)

    with pytest.raises(
        ValueError,
        match=(
            "Missing PagerDuty API key for example.pagerduty.com. "
            "Set PAGERDUTY_API_KEY_EXAMPLE_PAGERDUTY_COM."
        ),
    ):
        PagerDutyClient("example.pagerduty.com")


def test_pagerduty_client_api_key_name_replaces_hyphens(monkeypatch) -> None:
    monkeypatch.delenv("PAGERDUTY_API_KEY_TEAM_A_PAGERDUTY_COM", raising=False)

    with pytest.raises(
        ValueError,
        match=(
            "Missing PagerDuty API key for team-a.pagerduty.com. "
            "Set PAGERDUTY_API_KEY_TEAM_A_PAGERDUTY_COM."
        ),
    ):
        PagerDutyClient("team-a.pagerduty.com")


def test_slack_client_missing_api_key_names_workspace(monkeypatch) -> None:
    monkeypatch.delenv("SLACK_API_KEY_EXAMPLE_SLACK_COM", raising=False)

    with pytest.raises(
        ValueError,
        match=(
            "Missing Slack API key for example.slack.com. "
            "Set SLACK_API_KEY_EXAMPLE_SLACK_COM."
        ),
    ):
        SlackClient("example.slack.com", "C123")


def test_slack_client_api_key_name_replaces_hyphens(monkeypatch) -> None:
    monkeypatch.delenv("SLACK_API_KEY_TEAM_A_SLACK_COM", raising=False)

    with pytest.raises(
        ValueError,
        match=(
            "Missing Slack API key for team-a.slack.com. "
            "Set SLACK_API_KEY_TEAM_A_SLACK_COM."
        ),
    ):
        SlackClient("team-a.slack.com", "C123")
