import pytest

from emberpost.pagerduty import PagerDutyClient
from emberpost.slack import SlackClient


class RecordingSlackWebClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def users_lookupByEmail(  # noqa: N802 - Slack SDK method name
        self, *, email: str
    ) -> dict[str, object]:
        self.calls.append(("users_lookupByEmail", {"email": email}))
        return {"user": {"id": "U123"}}

    def chat_postMessage(  # noqa: N802 - Slack SDK method name
        self, **kwargs: object
    ) -> None:
        self.calls.append(("chat_postMessage", kwargs))

    def conversations_setTopic(  # noqa: N802 - Slack SDK method name
        self, **kwargs: object
    ) -> None:
        self.calls.append(("conversations_setTopic", kwargs))

    def usergroups_users_update(self, **kwargs: object) -> None:
        self.calls.append(("usergroups_users_update", kwargs))


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
        SlackClient("example.slack.com")


def test_slack_client_api_key_name_replaces_hyphens(monkeypatch) -> None:
    monkeypatch.delenv("SLACK_API_KEY_TEAM_A_SLACK_COM", raising=False)

    with pytest.raises(
        ValueError,
        match=(
            "Missing Slack API key for team-a.slack.com. "
            "Set SLACK_API_KEY_TEAM_A_SLACK_COM."
        ),
    ):
        SlackClient("team-a.slack.com")


def test_slack_client_delegates_workspace_operations_to_sdk(monkeypatch) -> None:
    web_client = RecordingSlackWebClient()
    received_tokens: list[str] = []

    def fake_web_client(*, token: str) -> RecordingSlackWebClient:
        received_tokens.append(token)
        return web_client

    monkeypatch.setenv("SLACK_API_KEY_EXAMPLE_SLACK_COM", "test-token")
    monkeypatch.setattr("emberpost.slack.WebClient", fake_web_client)

    client = SlackClient("example.slack.com")

    assert client.get_user_id_by_email("user@example.com") == "U123"
    client.post_message("C123", "hello")
    client.update_channel_topic("C456", "on-call")
    client.update_user_group("S123", ["U123", "U456"])

    assert received_tokens == ["test-token"]
    assert web_client.calls == [
        ("users_lookupByEmail", {"email": "user@example.com"}),
        ("chat_postMessage", {"channel": "C123", "text": "hello"}),
        ("conversations_setTopic", {"channel": "C456", "topic": "on-call"}),
        ("usergroups_users_update", {"usergroup": "S123", "users": "U123,U456"}),
    ]
