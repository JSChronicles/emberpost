import json
import os
from urllib.request import Request, urlopen


class MSTeamsClient:
    """Client for posting messages through a Microsoft Teams Workflow webhook."""

    def __init__(self, webhook_env: str) -> None:
        """Initialize the client from a configured webhook environment variable."""
        self.webhook_env = webhook_env
        self.webhook_url = self._webhook_url()

    def post_message(self, message: str) -> None:
        """Post a plain-text Adaptive Card through the configured workflow."""
        payload = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "contentUrl": None,
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.2",
                        "body": [{"type": "TextBlock", "text": message, "wrap": True}],
                    },
                }
            ],
        }
        request = Request(
            self.webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=30) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError(
                    f"Microsoft Teams webhook returned HTTP {response.status}"
                )

    def _webhook_url(self) -> str:
        webhook_url = os.getenv(self.webhook_env)
        if not webhook_url:
            raise ValueError(
                f"Missing Microsoft Teams Workflow webhook URL. Set {self.webhook_env}."
            )
        return webhook_url
