# Schedule Configuration

Start with the smallest valid YAML schedule, then add provider overrides only when a group must use a different destination. Use `examples/01-minimal.yaml` for one Slack destination or `examples/03-full.yaml` for mixed Slack and Microsoft Teams destinations.

## Required Structure

Each file requires:

- `id`: a stable, non-empty identifier.
- `schedule`: `daily`, `weekly`, or `manual`.
- `destination.provider.name`: `slack` or `msteams`.
- `destination.provider.options`: settings required by the selected provider.
- `pagerduty_tenant`: the PagerDuty tenant hostname.
- `schedule_groups`: one or more named groups.
- At least one `entries` item per group, with a PagerDuty `schedule_id` and display `label`.

The optional top-level fields are `suspended`, `message_header`, and `message_footer`. A suspended file is skipped. The header and footer wrap the rendered message or topic.

## Provider Destinations

The top-level `destination` is the complete default for every schedule group that omits its own destination. Provider-specific settings stay under `provider.options`:

```yaml
destination:
  provider:
    name: slack
    options:
      space: example.slack.com
      channel_id: C0123456789
      set_channel_topic: false
```

A group-level destination replaces the complete default. Use a Slack override for another workspace, channel, or topic mode, or select Microsoft Teams with a Workflows webhook environment variable:

```yaml
pagerduty_tenant: example.pagerduty.com

schedule_groups:
  Platform:
    entries:
      - schedule_id: PEXAMPLE1
        label: "Platform Primary"
  Database:
    destination:
      provider:
        name: slack
        options:
          space: database-team.slack.com
          channel_id: C0987654321
          set_channel_topic: true
    entries:
      - schedule_id: PEXAMPLE2
        label: "Database Primary"
  Incident:
    destination:
      provider:
        name: msteams
        options:
          webhook_env: MSTEAMS_WEBHOOK_INCIDENT
    entries:
      - schedule_id: PEXAMPLE3
        label: "Incident Commander"
```

Slack messages use Slack mentions. Slack channel topics and Microsoft Teams messages use PagerDuty display names. Teams webhook URLs remain in environment variables and are never stored in YAML.

## User Groups And Alternating Labels

Set `slack_group_id` on a schedule group to replace that Slack user group's membership with the resolved on-call users. The group's effective provider must be Slack.

Set `swap_on_odd_weeks: true` only on a group with exactly two entries. Emberpost swaps their display order during odd ISO week numbers; it does not change the PagerDuty schedules themselves.

Rules:

- Start from the minimal example and add optional fields intentionally.
- Keep provider-specific settings under `destination.provider.options`.
- Use the top-level `destination` as the complete default for every group.
- Add a complete group-level `destination` only when the group must replace the default.
- Use Slack `set_channel_topic: false` for messages and `true` for channel-topic replacement.
- Reference Teams webhook URLs through `webhook_env`; never put a URL in YAML.
- Use `slack_group_id` only when Emberpost should replace a Slack user group's membership.
- Use `swap_on_odd_weeks: true` only with exactly two entries.
- Keep credentials out of schedule files.
