import os
import re

from slack_sdk import WebClient


class SlackClient:
    def __init__(self, slack_space: str, channel_id: str) -> None:
        self.slack_space = slack_space
        self.channel_id = channel_id
        self.client = WebClient(token=self._api_key())

    def get_user_id_by_email(self, email: str) -> str:
        response = self.client.users_lookupByEmail(email=str(email))
        return response["user"]["id"]

    def post_message(self, message: str) -> None:
        self.client.chat_postMessage(channel=self.channel_id, text=message)

    def update_channel_topic(self, topic: str) -> None:
        self.client.conversations_setTopic(channel=self.channel_id, topic=topic)

    def update_user_group(self, user_group_id: str, user_ids: list[str]) -> None:
        self.client.usergroups_users_update(
            usergroup=user_group_id, users=",".join(user_ids)
        )

    def _api_key(self) -> str:
        slack_space_env_name = re.sub(r"[^A-Z0-9]", "_", self.slack_space.upper())
        env_var = f"SLACK_API_KEY_{slack_space_env_name}"
        api_key = os.getenv(env_var)
        if not api_key:
            raise ValueError(
                f"Missing Slack API key for {self.slack_space}. Set {env_var}."
            )
        return api_key
