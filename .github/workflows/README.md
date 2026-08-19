# GitHub workflows

This directory contains automation for AudioBard.

## `notifications.yml` — Discord notifier

Sends an embed to a Discord channel whenever a PR or issue is opened, reopened, closed, or labeled (only `ethics-review` labels trigger notifications to avoid spam).

### Setup

1. **Create a Discord webhook**:
   - Server settings → Integrations → Webhooks → New webhook
   - Copy the URL (looks like `https://discord.com/api/webhooks/1234567/abcdef...`)

2. **Add it as a repo secret**:
   - Repo → Settings → Secrets and variables → Actions → New repository secret
   - Name: `DISCORD_WEBHOOK_URL`
   - Value: the webhook URL from step 1

3. (Optional) **Ping a role on every notification**:
   - Add another secret `NOTIFY_ROLE_ID` with the role ID (right-click role in Discord → "Copy role ID"; requires Developer Mode)
   - The bot will mention `@role` in the message

### What gets sent

- **PR opened/reopened/closed/ready_for_review/review_requested**: title, number, author, action verb, URL. Color: green (merged), gray (closed), blue (other).
- **Issue opened/reopened/closed**: same fields plus labels. Color: orange if `ethics-review` label, red otherwise, gray if closed.
- **Issue labeled with `ethics-review`**: triggers notification (other labels are ignored).

### Disabling

If you don't want notifications, simply remove the `DISCORD_WEBHOOK_URL` secret — the workflow exits cleanly with a warning instead of failing.

## Other workflows (planned)

- `ci.yml` — lint + type-check + test on Python 3.10/3.11/3.12 (Phase 1.1)
- `benchmark.yml` — weekly cron + manual trigger for attribution accuracy (Phase 3.3)
- `release.yml` — automated PyPI publish on tag push (Phase 4.3)
