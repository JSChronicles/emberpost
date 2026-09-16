from dataclasses import dataclass

from emberpost.schedule_config import ScheduleConfig


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


def fake_slack_clients(
    config: ScheduleConfig, slack_client: FakeSlackClient
) -> dict[str, FakeSlackClient]:
    return {
        group.resolve_slack_config(config.slack).slack_space: slack_client
        for group in config.pagerduty.schedule_groups.values()
    }


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
