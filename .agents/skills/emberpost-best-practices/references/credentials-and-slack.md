# Credentials And Slack Setup

Keep every token in a tenant- or workspace-specific environment variable. Never place tokens in schedule YAML, command arguments, logs, examples, or committed files.

## PagerDuty

Convert the configured tenant to uppercase and replace every non-alphanumeric character with an underscore:

```text
example.pagerduty.com -> PAGERDUTY_API_KEY_EXAMPLE_PAGERDUTY_COM
```

Set that environment variable to a PagerDuty API token that can read schedules, current on-call assignments, and users.

## Slack

Use the same conversion for every configured Slack workspace:

```text
example.slack.com -> SLACK_API_KEY_EXAMPLE_SLACK_COM
database-team.slack.com -> SLACK_API_KEY_DATABASE_TEAM_SLACK_COM
```

Each variable holds the bot token for that workspace. A configuration that routes groups to multiple workspaces needs one token variable per workspace.

The Slack app needs permissions for the features being used:

- Posting messages: `chat:write`; add `chat:write.public` if the bot will post without joining public channels.
- Resolving PagerDuty email addresses to Slack users: `users:read` and `users:read.email`.
- Changing channel topics: `channels:write.topic` for public channels and `groups:write.topic` for private channels.
- Updating Slack user groups: `usergroups:write`.

Install the app into each target workspace and invite it to channels when the workspace's policy or channel type requires membership. Obtain a channel ID from the channel's copied Slack link; it is the segment beginning with `C` in a URL such as `https://example.slack.com/archives/C0123456789`.

When a token is missing, Emberpost reports the exact environment variable it expected. Treat tokens shown in diagnostic output as exposed and rotate them.

Rules:

- Create one PagerDuty environment variable per configured tenant.
- Create one Slack environment variable per configured workspace, including workspaces used only by group overrides.
- Derive environment-variable names by uppercasing the hostname and replacing non-alphanumeric characters with underscores.
- Grant only the Slack scopes needed for the configured message, topic, lookup, and user-group features.
- Install the Slack app in every target workspace and give it access to every target channel.
- Never ask a user to paste a token into chat. Ask them to verify the named variable locally and share only sanitized errors.
