# Schedule Configuration

Start with the smallest valid YAML schedule, then add routing and output behavior only when needed. Use `examples/01-minimal.yaml` for one destination or `examples/03-full.yaml` for the available optional behavior.

## Required Structure

Each file requires:

- `id`: a stable, non-empty identifier.
- `schedule`: `daily`, `weekly`, or `manual`.
- `pagerduty.tenant`: the PagerDuty tenant hostname.
- `pagerduty.schedule_groups`: one or more named groups.
- At least one `entries` item per group, with a PagerDuty `schedule_id` and display `label`.
- `slack.slack_space`: the Slack workspace hostname.
- `slack.slack_channel_id`: the default destination channel ID.

The optional top-level fields are `suspended`, `message_header`, and `message_footer`. A suspended file is skipped. The header and footer wrap the rendered message or topic.

## Slack Destinations

The top-level `slack` block supplies defaults to all schedule groups:

```yaml
slack:
  slack_space: example.slack.com
  slack_channel_id: C0123456789
  set_channel_topic: false
```

A group may override any destination field independently; omitted values inherit from the top-level block:

```yaml
pagerduty:
  tenant: example.pagerduty.com
  schedule_groups:
    Platform:
      entries:
        - schedule_id: PEXAMPLE1
          label: "Platform Primary"
    Database:
      slack_space: database-team.slack.com
      slack_channel_id: C0987654321
      set_channel_topic: true
      entries:
        - schedule_id: PEXAMPLE2
          label: "Database Primary"
```

`set_channel_topic: false` posts a message containing Slack mentions. `set_channel_topic: true` replaces the channel topic and uses PagerDuty display names.

Avoid repeating the same Slack destination in every schedule group. Prefer top-level defaults with only the fields that differ declared as group overrides.

## User Groups And Alternating Labels

Set `slack_group_id` on a schedule group to replace that Slack user group's membership with the resolved on-call users. This can be combined with either message or topic output.

Set `swap_on_odd_weeks: true` only on a group with exactly two entries. Emberpost swaps their display order during odd ISO week numbers; it does not change the PagerDuty schedules themselves.

Rules:

- Start from the minimal example and add optional fields intentionally.
- Keep the top-level `slack` block as the default destination for every group.
- Add a group-level Slack field only when that group should differ from the corresponding default.
- Use `set_channel_topic: false` for messages and `true` for channel-topic replacement.
- Use `slack_group_id` only when Emberpost should replace a Slack user group's membership.
- Use `swap_on_odd_weeks: true` only with exactly two entries.
- Keep credentials out of schedule files.
