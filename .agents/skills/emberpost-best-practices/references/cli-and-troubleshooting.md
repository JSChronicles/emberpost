# CLI And Troubleshooting

Inspect the CLI first, then use a dry run before allowing Emberpost to write to Slack.

## Install And Inspect

In a source checkout, install dependencies and run Emberpost with uv:

```console
uv sync
uv run emberpost --version
uv run emberpost --help
```

When installed as a package, invoke `emberpost` directly instead of prefixing commands with `uv run`.

## Run Schedules

Avoid starting with a live write:

```console
uv run emberpost --schedule-file schedules/oncall.yaml --frequency weekly
```

Prefer a dry run first:

```console
uv run emberpost --schedule-file schedules/oncall.yaml --frequency weekly --dry-run
```

After verifying the rendered output and effective Slack destinations, omit `--dry-run` to write to Slack:

```console
uv run emberpost --schedule-file schedules/oncall.yaml --frequency weekly
```

Pass multiple files after `--schedule-file` to process them in one invocation. Use `--log-level DEBUG` with a dry run when troubleshooting. Valid frequency values are `daily`, `weekly`, and `manual`; a file runs only when its `schedule` value matches the command frequency.

## Automation

Run the same command from a scheduler at the desired cadence, selecting the matching `--frequency`. Keep credentials in the scheduler's secret or environment-variable facility. Use separate invocations for different cadences when both daily and weekly files exist.

## Common Failures

- **Missing API key:** Set the exact environment variable named by the error. Multiple PagerDuty tenants or Slack workspaces require separate variables.
- **Configuration validation failure:** Compare the YAML with `examples/01-minimal.yaml` and check field spelling, allowed frequency values, hostnames, required entries, and the two-entry requirement for `swap_on_odd_weeks`.
- **File was skipped:** Confirm `suspended` is not true and `--frequency` matches the file's `schedule` value.
- **No on-call user found:** Verify the PagerDuty schedule ID and confirm the schedule currently resolves an on-call user.
- **Slack user lookup failed:** Confirm the PagerDuty user's email matches their Slack account and the app has `users:read.email`.
- **Slack permission or channel error:** Verify the bot token belongs to the configured workspace, the channel ID is correct, the app has the required scope, and the bot has channel access.
- **Wrong destination:** Resolve each group's destination by applying its explicit overrides over the top-level `slack` defaults.

Rules:

- Run `--version` or `--help` when verifying the installation or available arguments.
- Use `--dry-run` before the first live run and after configuration or destination changes.
- Match `--frequency` to each file's `schedule` value.
- Use separate scheduled invocations for different cadences.
- Use `--log-level DEBUG` with a dry run when more diagnostic detail is needed.
- Verify rendered output and effective Slack destinations before omitting `--dry-run`.
- Do not solve credential or permission failures by requesting a user's token. Ask them to verify the named variable or permission locally and share only sanitized errors.
