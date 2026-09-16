from dataclasses import dataclass

from emberpost.schedule_config import ScheduleConfig


@dataclass(frozen=True)
class FakePagerDutyOnCall:
    """Resolved PagerDuty identity used by tests."""

    email: str
    name: str


class FakePagerDutyClient:
    """Record PagerDuty schedule requests and return stable identities."""

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
    """Record Slack reads and writes made by dispatch tests."""

    def __init__(self) -> None:
        self.requested_emails: list[str] = []
        self.messages: list[str] = []
        self.message_channels: list[str] = []
        self.topics: list[str] = []
        self.topic_channels: list[str] = []
        self.user_group_updates: list[tuple[str, list[str]]] = []

    def get_user_id_by_email(self, email: str) -> str:
        self.requested_emails.append(email)
        return {"one@example.com": "U1", "two@example.com": "U2"}[email]

    def post_message(self, channel_id: str, message: str) -> None:
        self.message_channels.append(channel_id)
        self.messages.append(message)

    def update_channel_topic(self, channel_id: str, topic: str) -> None:
        self.topic_channels.append(channel_id)
        self.topics.append(topic)

    def update_user_group(self, user_group_id: str, user_ids: list[str]) -> None:
        self.user_group_updates.append((user_group_id, user_ids))


class FakeMSTeamsClient:
    """Record Microsoft Teams messages made by dispatch tests."""

    def __init__(self, webhook_env: str) -> None:
        self.webhook_env = webhook_env
        self.messages: list[str] = []

    def post_message(self, message: str) -> None:
        self.messages.append(message)


def slack_destination(
    *,
    space: str = "example.slack.com",
    channel_id: str = "C123",
    set_channel_topic: bool = False,
) -> dict[str, object]:
    """Return a Slack destination configuration dictionary."""
    return {
        "provider": {
            "name": "slack",
            "options": {
                "space": space,
                "channel_id": channel_id,
                "set_channel_topic": set_channel_topic,
            },
        }
    }


def msteams_destination(webhook_env: str = "MSTEAMS_WEBHOOK_TEST") -> dict[str, object]:
    """Return a Microsoft Teams destination configuration dictionary."""
    return {"provider": {"name": "msteams", "options": {"webhook_env": webhook_env}}}


def minimal_config(config_id: str = "test") -> ScheduleConfig:
    """Return a minimal weekly Slack schedule configuration."""
    return ScheduleConfig.from_dict(
        {
            "id": config_id,
            "schedule": "weekly",
            "destination": slack_destination(),
            "pagerduty_tenant": "example.pagerduty.com",
            "schedule_groups": {
                "TEAM": {"entries": [{"schedule_id": "P1", "label": "First"}]}
            },
        }
    )
