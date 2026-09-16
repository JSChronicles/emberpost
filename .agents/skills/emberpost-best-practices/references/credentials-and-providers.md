# Credentials And Provider Setup

Keep every token and webhook URL in an environment variable. Never place credentials in schedule YAML, command arguments, logs, examples, or committed files.

## PagerDuty

Convert the configured tenant to uppercase and replace every non-alphanumeric character with an underscore:

```text
example.pagerduty.com -> PAGERDUTY_API_KEY_EXAMPLE_PAGERDUTY_COM
```

Set that environment variable to a PagerDuty API token that can read schedules, current on-call assignments, and users.

## Slack

Apply the same conversion to `destination.provider.options.space` for every effective Slack destination:

```text
example.slack.com -> SLACK_API_KEY_EXAMPLE_SLACK_COM
database-team.slack.com -> SLACK_API_KEY_DATABASE_TEAM_SLACK_COM
```

Each variable holds the bot token for that workspace. The Slack app needs only the permissions used by the configured features:

- Posting messages: `chat:write`; add `chat:write.public` if the bot posts without joining public channels.
- Resolving PagerDuty email addresses to Slack users: `users:read` and `users:read.email`.
- Changing channel topics: `channels:write.topic` for public channels and `groups:write.topic` for private channels.
- Updating Slack user groups: `usergroups:write`.

Install the app in every target workspace and give it access to every target channel.

## Microsoft Teams

Open **Workflows** in Teams and choose the incoming-webhook template for the intended channel or chat. Microsoft provides separate templates for channels, chats, and different authentication modes; the webhook templates do not require a premium license. Select **Anyone** as the authentication mode because Emberpost calls the secret webhook URL without an OAuth token. Choose the destination, save the workflow, copy its generated URL, and add co-owners so the workflow does not become orphaned.

Store the generated webhook URL in the environment variable named by `destination.provider.options.webhook_env`. The URL is already bound to the workflow's selected chat or channel, so Emberpost does not require Team or channel IDs. Refer users to Microsoft's [incoming webhook setup guide](https://support.microsoft.com/en-us/workflows/send-messages-in-teams-using-incoming-webhooks) when they need current UI instructions.

Rules:

- Create one PagerDuty environment variable per configured tenant.
- Create one Slack environment variable per effective Slack workspace.
- Create one Teams environment variable per Workflows webhook.
- Grant only the Slack scopes needed by the configured features.
- Never ask a user to paste a token or webhook URL into chat. Ask them to verify the named variable locally and share only sanitized errors.
