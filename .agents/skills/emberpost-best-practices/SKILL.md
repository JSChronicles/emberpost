---
name: emberpost-best-practices
description: Guides users through installing, configuring, running, automating, and troubleshooting Emberpost. Use when asked how to use Emberpost, write schedule YAML, configure PagerDuty, Slack, or Microsoft Teams access, run the CLI, or understand its output. Do not use for implementation, code review, packaging, or release engineering.
metadata:
  author: JSChronicles
  version: "0.1"
---

# Emberpost Best Practices

Help users operate Emberpost safely and correctly. Emberpost resolves current PagerDuty on-call assignments and publishes them through Slack or Microsoft Teams destinations.

## Core Rules

- Start users with `examples/01-minimal.yaml` and add optional behavior only when requested.
- Recommend `--dry-run` before any command that writes to a provider. A dry run requires the configured credentials and may query PagerDuty and Slack, but it does not post messages, change topics, or update user groups.
- Match `--frequency` to the schedule file's `schedule` value. Explain that nonmatching and suspended configurations are intentionally skipped.
- Treat the top-level `destination` as the default. A group-level `destination` is a complete replacement and may select Slack or Microsoft Teams.
- Keep provider-specific settings under `destination.provider.options`. For Slack, `set_channel_topic: false` posts a message and `true` replaces the channel topic.
- Never ask users to paste API tokens or webhook URLs into chat or commit them to schedule files. Use the environment variables described in the credentials reference.
- Do not claim that a run succeeded unless command output confirms it. When helping execute Emberpost, preserve normal authorization boundaries for external writes.

## Workflow

1. Determine whether the user needs installation, configuration, credentials, execution, automation, or troubleshooting help.
2. Read only the reference that covers that task.
3. Prefer a dry run and explain the expected destination and action before a live run.
4. If diagnosing a failure, use the exact error and the selected tenant, workspace, channel, frequency, and schedule file without exposing secrets.

## Reference Loading

- For schedule YAML, provider destinations, defaults, group overrides, topics, and user groups, read [references/configuration.md](references/configuration.md).
- For PagerDuty tokens, Slack tokens and permissions, and Teams Workflows webhooks, read [references/credentials-and-providers.md](references/credentials-and-providers.md).
- For installation, CLI commands, dry runs, automation, and common failures, read [references/cli-and-troubleshooting.md](references/cli-and-troubleshooting.md).

## Response Behavior

Give users the exact configuration or command needed for their situation. Clearly distinguish dry runs from commands that write externally, identify whether a group inherits or completely replaces the default destination, and keep credentials and webhook URLs out of examples and diagnostic output.
