# emberpost

<a name="readme-top"></a>

<!-- PROJECT SHIELDS -->
[![pytest][pytest-badge]][pytest-url]
[![ruff][ruff-badge]][ruff-url]
[![release][release-badge]][release-url]
[![PyPI][pypi-badge]][pypi-url]
[![prek][prek-badge]][prek-url]


<!-- PROJECT LOGO -->
<br />
<div align="center">
  <img src="images/logo.png" alt="Logo" width="350" height="325">
  </a>

  <h3 align="center">README</h3>

  <p align="center">
    <a href="https://github.com/JSChronicles/emberpost"><strong>Explore the docs &raquo;</strong></a>
    <br />
    <a href="https://github.com/JSChronicles/emberpost/issues/new?labels=Bug%2CNeeds+Triage&projects=&template=bug.yaml&title=%5BBUG%5D+%3Ctitle%3E">Report Bug</a>
    &middot;
    <a href="https://github.com/JSChronicles/emberpost/issues/new?labels=enhancement%2Cfeature+request&projects=&template=feature.yaml&title=%5BFEATURE%5D%3A+">Request Feature</a>
  </p>
</div>

## Introduction

`emberpost` keeps Slack and Microsoft Teams aligned with the current PagerDuty on-call rotation. It reads a YAML schedule definition, resolves the active on-call users from PagerDuty, and publishes each schedule group to its effective provider destination.

Use it to post an on-call summary to Slack or Microsoft Teams, update a Slack channel topic, or keep a Slack user group in sync with the people currently carrying the pager. Schedule files can be marked as `daily`, `weekly`, or `manual`, which makes the same command safe to run from automation while only processing the rotations due for that run.

Start with [examples/01-minimal.yaml](examples/01-minimal.yaml) for the smallest working schedule shape, then add channel topics, user groups, headers, or footers as needed.

## Usage

Install the project and its dependencies with [uv](https://docs.astral.sh/uv/):

```console
uv sync
```

Commands can then be run through `uv run`, which uses the project environment automatically. The `--frequency` flag is an automation guardrail: a `weekly` schedule is skipped during a `daily` run. For a Slack provider, set `destination.provider.options.set_channel_topic: true` to update a channel topic instead of posting a message.

Run a dry run before writing to a destination provider:

```console
uv run emberpost --schedule-file schedules/oncall.yaml --frequency weekly --dry-run
```

Run the weekly schedule and update its configured destinations:

```console
uv run emberpost --schedule-file schedules/oncall.yaml --frequency weekly
```

Process more than one schedule file in a single run:

```console
uv run emberpost --schedule-file schedules/oncall.yaml examples/03-full.yaml --frequency weekly
```

Run a manual schedule file:

```console
uv run emberpost --schedule-file examples/01-minimal.yaml --frequency manual --dry-run
```

Run with more logging while troubleshooting:

```console
uv run emberpost --schedule-file schedules/oncall.yaml --frequency weekly --dry-run --log-level DEBUG
```

The top-level `destination` is used by every schedule group that does not define a complete override. Provider-specific settings live under `provider.options`:

```yaml
pagerduty_tenant: example.pagerduty.com

destination:
  provider:
    name: slack
    options:
      space: example.slack.com
      channel_id: C0123456789
      set_channel_topic: false

schedule_groups:
  Platform Coverage:
    entries:
      - schedule_id: PEXAMPLE1
        label: "Primary Responder"
```

Add `slack_group_id` to a group using an effective Slack destination to synchronize that group's resolved users to a Slack user group. A group may replace the default with another complete Slack or Microsoft Teams destination:

```yaml
pagerduty_tenant: example.pagerduty.com

destination:
  provider:
    name: slack
    options:
      space: example.slack.com
      channel_id: C0123456789
      set_channel_topic: false

schedule_groups:
  Platform Coverage:
    slack_group_id: S0123456789
    entries:
      - schedule_id: PEXAMPLE1
        label: "Primary Responder"
  Database Coverage:
    destination:
      provider:
        name: slack
        options:
          space: database-team.slack.com
          channel_id: C0987654321
          set_channel_topic: true
    entries:
      - schedule_id: PEXAMPLE2
        label: "Database Responder"
  Incident Coverage:
    destination:
      provider:
        name: msteams
        options:
          webhook_env: MSTEAMS_WEBHOOK_INCIDENT
    entries:
      - schedule_id: PEXAMPLE3
        label: "Incident Commander"
```

Here, `Platform Coverage` uses the default Slack destination, `Database Coverage` replaces it with another Slack channel topic, and `Incident Coverage` posts through a Microsoft Teams Workflows webhook.

## Setting up your Slack Bot

### Bot Information
This section is just an example manifest, to show what is needed to get the bot working for the posting use.

```yaml
display_information:
  name: Notification
  description: Notification webhook/app
  background_color: "#2c2d30"
features:
  bot_user:
    display_name: Notification
    always_online: false
oauth_config:
  scopes:
    bot:
      - channels:write.topic
      - chat:write
      - chat:write.customize
      - chat:write.public
      - files:read
      - files:write
      - users:read
      - users:read.email
      - groups:write.topic
      - mpim:history
      - im:write.topic
      - mpim:write.topic
      - usergroups:write
  pkce_enabled: false
settings:
  interactivity:
    is_enabled: true
    request_url: https://example.com/ignore
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false
  is_mcp_enabled: false
```

### Create a slack app

1. Set Up Your App
   1. Go to the [Slack API portal](https://api.slack.com/apps).
   1. Click [Create New App](https://api.slack.com/apps?new_app=1).
   1. Choose From scratch and give your app a name and select the workspace where it will be installed.
      1. Or if you are choosing to copy one of the above templates/manifests then you can choose From a manifest and speed up the process.
1. Configure App Features
   1. Depending on what your app needs to do, you can enable features like:
      1. Bot Token: For sending messages and interacting with users.
      1. Event Subscriptions: To listen for events like messages or reactions.
1. Set Permissions (Scopes)
   1. Go to OAuth & Permissions.
   1. Add the necessary OAuth scopes (e.g., chat:write, commands, users:read).
      1. These define what your app is allowed to do in the workspace.
1. Install the App
   1. Still in the OAuth & Permissions section, click "Install to Workspace".
   1. Authorize the app to access your workspace.
   1. A Slack Admin for your organization will need to review the request
   1. You’ll receive a Bot User OAuth Token once approved
      1. save this securely.

### Configure Slack credentials

For each configured Slack workspace, uppercase the hostname and replace non-alphanumeric characters with underscores. Store its bot token in the resulting environment variable:

```text
example.slack.com -> SLACK_API_KEY_EXAMPLE_SLACK_COM
```

To find a channel ID, copy the Slack channel link. The final path segment beginning with `C` is the channel ID.

## Setting up Microsoft Teams

In Teams, open **Workflows**, search for an incoming-webhook template, and choose the template that posts to your intended channel or chat. Microsoft provides separate templates for channels, chats, and different authentication modes; these Teams webhook templates do not require a premium license. Select **Anyone** as the trigger authentication mode because Emberpost authenticates with the secret webhook URL and does not send an OAuth token. Choose the destination, save the workflow, add co-owners for operational continuity, and copy the generated webhook URL.

Store the URL in the environment variable named by `webhook_env`:

```yaml
destination:
  provider:
    name: msteams
    options:
      webhook_env: MSTEAMS_WEBHOOK_INCIDENT
```

Do not store a Teams webhook URL directly in schedule YAML. Each Teams Workflows webhook is bound to the chat or channel selected in its workflow, so no separate Team or channel ID is required. See Microsoft's [incoming webhook setup guide](https://support.microsoft.com/en-us/workflows/send-messages-in-teams-using-incoming-webhooks) for the current template flow.



<!-- MARKDOWN LINKS & IMAGES -->
[pytest-badge]:https://github.com/JSChronicles/emberpost/actions/workflows/pytest.yaml/badge.svg?branch=main
[pytest-url]:https://github.com/JSChronicles/emberpost/actions/workflows/pytest.yaml
[ruff-badge]:https://github.com/JSChronicles/emberpost/actions/workflows/ruff.yaml/badge.svg?branch=main
[ruff-url]:https://github.com/JSChronicles/emberpost/actions/workflows/ruff.yaml
[release-badge]:https://github.com/JSChronicles/emberpost/actions/workflows/release.yaml/badge.svg?branch=main
[release-url]:https://github.com/JSChronicles/emberpost/actions/workflows/release.yaml
[pypi-badge]:https://img.shields.io/pypi/v/emberpost
[pypi-url]:https://pypi.org/project/emberpost/

[prek-badge]:https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/j178/prek/master/docs/assets/badge-v0.json
[prek-url]:https://github.com/j178/prek
