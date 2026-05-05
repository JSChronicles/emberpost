# emberpost

<a name="readme-top"></a>

<!-- PROJECT SHIELDS -->
[![pytest][pytest-badge]][pytest-url]
[![ruff][ruff-badge]][ruff-url]
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

`emberpost` keeps Slack aligned with the current PagerDuty on-call rotation. It reads a YAML schedule definition, resolves the active on-call users from PagerDuty, maps them to Slack users by email, and then updates the configured Slack channel.

Use it to post an on-call summary, update a channel topic, or keep a Slack user group in sync with the people currently carrying the pager. Schedule files can be marked as `daily`, `weekly`, or `manual`, which makes the same command safe to run from automation while only processing the rotations due for that run.

Start with [examples/01-minimal.yaml](examples/01-minimal.yaml) for the smallest working schedule shape, then add channel topics, user groups, headers, or footers as needed.

## Usage
1. When using the uv tool, there are several ways to run and install dependencies. Here are a few examples:
   1. Manual setup (similar to pip-tools):
      1. Create a Python virtual environment: uv venv or python -m venv .venv
      1. Activate the virtual environment: .\.venv\Scripts\activate.ps1
      1. Install dependencies: uv pip install --requirements pyproject.toml
1. uv sync:
   1. Sync the project's dependencies with the environment: uv sync
   1. Activate the virtual environment: .venv\Scripts\activate
1. uv run:
   1. Run a command in the project environment.: `uv run example.py <args>`
      1. uv run emberpost --schedule-file schedules/oncall.yaml --frequency weekly --dry-run
   1. Note that if you use uv run in a project, i.e. a directory with a pyproject.toml, it will install the current project before running the script.


- The `--frequency` flag is a guardrail for automation. A schedule file marked `weekly` is skipped when the command runs with `--frequency daily`, which lets daily and weekly jobs share the same command shape.
- Set `slack.set_channel_topic: true` in the schedule file to update the channel topic instead of posting a message:

Run a dry run before writing to Slack:
```python
uv run emberpost --schedule-file schedules/oncall.yaml --frequency weekly --dry-run
```

Run the weekly schedule and update Slack:
```python
uv run emberpost --schedule-file schedules/oncall.yaml --frequency weekly
```

Process more than one schedule file in a single run:
```python
uv run emberpost --schedule-file schedules/oncall.yaml examples/03-full.yaml --frequency weekly
```

Run a manual schedule file:
```python
uv run emberpost --schedule-file examples/01-minimal.yaml --frequency manual --dry-run
```

Run with more logging while troubleshooting:
```python
uv run emberpost --schedule-file schedules/oncall.yaml --frequency weekly --dry-run --log-level DEBUG
```

Add `slack_group_id` under a schedule group heading to sync that heading's resolved users to a Slack user group:

```yaml
pagerduty:
  tenant: example.pagerduty.com
  schedule_groups:
    Platform Coverage:
      slack_group_id: S0123456789
      entries:
        - schedule_id: PEXAMPLE1
          label: "Primary Responder"
        - schedule_id: PEXAMPLE2
          label: "Backup Responder"
```

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

### Setup GitHub Repository Slack Notification
1. Create a slack app, if you haven't already
1. Go to the GitHub repository → Select Settings → select Secrets and variables → Select Actions → Add these three secrets under New repository secret and under Dependabot
   1. `SLACK_BOT_TOKEN` - This is the authentication token you receive after creating and installing your Slack app. It allows your app to interact with the Slack API and post messages as a bot.
   1. `SLACK_CHANNEL_ID` - The ID of the primary Slack channel where you want production alerts or notifications to be sent.
      1. To find a channel ID, right-click on any Slack channel you have access to and select Copy then Copy link. The URL will look something like this: `https://xxxxx.slack.com/archives/Cxxxxx`. The part at the end that starts with a 'C' is the channel ID you’ll need.
   1. `SLACK_CHANNEL_ID_TEST` - An optional separate channel ID used for testing purposes. It's recommended to use this during development to avoid cluttering your main channel with test messages.



<!-- MARKDOWN LINKS & IMAGES -->
[pytest-badge]:https://github.com/JSChronicles/emberpost/actions/workflows/pytest.yaml/badge.svg?branch=main
[pytest-url]:https://github.com/JSChronicles/emberpost/actions/workflows/pytest.yaml
[ruff-badge]:https://github.com/JSChronicles/emberpost/actions/workflows/ruff.yaml/badge.svg?branch=main
[ruff-url]:https://github.com/JSChronicles/emberpost/actions/workflows/ruff.yaml

[prek-badge]:https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/j178/prek/master/docs/assets/badge-v0.json
[prek-url]:https://github.com/j178/prek
