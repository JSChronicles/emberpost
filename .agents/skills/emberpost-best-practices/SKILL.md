---
name: emberpost-best-practices
description: Guides users through installing, configuring, running, automating, and troubleshooting Emberpost. Use when asked how to use Emberpost, write schedule YAML, configure PagerDuty or Slack access, run the CLI, or understand its output. Do not use for implementation, code review, packaging, or release engineering.
metadata:
  author: JSChronicles
  version: "0.1"
---

# Emberpost Best Practices

Help users operate Emberpost safely and correctly. Emberpost resolves current PagerDuty on-call assignments and publishes them to Slack as messages, channel topics, or Slack user-group membership.

## Core Rules

- Start users with `examples/01-minimal.yaml` and add optional behavior only when requested.
- Recommend `--dry-run` before any command that writes to Slack. A dry run still needs valid credentials and may query PagerDuty and Slack, but it does not post messages, change topics, or update user groups.
- Match `--frequency` to the schedule file's `schedule` value. Explain that nonmatching and suspended configurations are intentionally skipped.
- Treat the top-level `slack` block as the default destination. A schedule group may independently override `slack_space`, `slack_channel_id`, and `set_channel_topic`.
- Explain that `set_channel_topic: false` posts a message, while `true` replaces the channel topic.
- Never ask users to paste API tokens into chat or commit them to schedule files. Use the tenant- and workspace-specific environment variables described in the credentials reference.
- Do not claim that a run succeeded unless command output confirms it. When helping execute Emberpost, preserve normal authorization boundaries for external writes.

## Workflow

1. Determine whether the user needs installation, configuration, credentials, execution, automation, or troubleshooting help.
2. Read only the reference that covers that task.
3. Prefer a dry run and explain the expected destination and action before a live run.
4. If diagnosing a failure, use the exact error and the selected tenant, workspace, channel, frequency, and schedule file without exposing secrets.

## Reference Loading

- For schedule YAML, fields, defaults, group overrides, topics, and user groups, read [references/configuration.md](references/configuration.md).
- For PagerDuty tokens, Slack tokens, workspace-specific environment variables, and Slack app permissions, read [references/credentials-and-slack.md](references/credentials-and-slack.md).
- For installation, CLI commands, dry runs, automation, and common failures, read [references/cli-and-troubleshooting.md](references/cli-and-troubleshooting.md).

## Response Behavior

Give users the exact configuration or command needed for their situation. Clearly distinguish dry runs from commands that write to Slack, identify which destination settings are inherited or overridden, and keep credentials out of examples and diagnostic output.
