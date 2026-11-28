# Portalis

The official bot for **SMP Portal** — tickets, freelancer applications and
server partnering/advertising, in bright red with full branding.

## Features

- **Tickets** — `/panel Tickets` posts a branded panel with a select menu
  (Support / Partnership). One open ticket per user, private channel per
  ticket, **Claim** and **Close** controls, and a text transcript posted to
  the log channel on close.
- **Freelancer applications** — `/panel Freelancer applications` posts a
  panel with an **Apply** button that opens a form. Submissions land in the
  review channel with **Approve / Deny** buttons; approval grants the
  Freelancer role, denial asks for a reason. The applicant is DM'd either way.
- **Partner / advertise** — `/panel Partner / advertise` posts a panel where
  server owners submit their server. Approval posts a branded ad (invite +
  member count) to the ads channel and grants the Partner role.

Buttons and menus are persistent — panels keep working across restarts, and
pending applications/partner requests get their review buttons re-attached
on boot.

## Setup

1. Create an application at the
   [Discord Developer Portal](https://discord.com/developers/applications),
   add a bot, copy the token.
2. Under **Bot → Privileged Gateway Intents**, enable **Server Members Intent**.
3. Invite the bot with the `bot` + `applications.commands` scopes
   (`Manage Channels`, `Manage Roles`, `Send Messages` permissions).
4. Install deps and set env:

   ```
   pip install -r requirements.txt
   copy .env.example .env   # then paste your token
   copy config.example.json config.json
   ```

   Set `DATABASE_URL` in `.env` to your host's Postgres connection string —
   the bot creates its table automatically. If unset, data falls back to
   `data/data.json`.

5. Fill in `config.json` with your server's IDs (right-click → Copy Channel/Role ID
   with Developer Mode on):

   | Key | What |
   |---|---|
   | `guild_id` | Your server ID — makes commands register instantly |
   | `staff_role_id` | Role that can claim tickets and review submissions |
   | `freelancer_role_id` | Granted on application approval |
   | `partner_role_id` | Granted on partner approval |
   | `ticket_category_id` | Category new ticket channels are created in |
   | `ticket_log_channel_id` | Where close transcripts are posted |
   | `applications_channel_id` | Staff review channel for applications |
   | `partners_channel_id` | Staff review channel for partner requests |
   | `ads_channel_id` | Where approved partner ads are posted |

6. Run `python app.py`, then post panels with `/panel`.

## Branding

Embeds use SMP Portal red (`#ED1C24`) and attach `assets/banner.webp` +
`assets/pfp.webp`. Swap the files in `assets/` to rebrand — keep the
filenames and everything updates.
