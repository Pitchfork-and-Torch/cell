# cell

Give this Grok Build instance a real PSTN phone number. SMS first, voice second. No physical handset required.

```
cell status
cell send +15551234567 "hello" --yes
cell inbox --limit 20
cell watch
cell call +15551234567 --say "This is Grok." --yes
```

## What it is

A Python CLI (`cell`) plus a Grok skill and optional MCP server. The default backend is **Twilio** (mature SMS + voice + number inventory + message history). **Telnyx** is wired as a cheaper second backend. A **USB modem** backend is a reserved stub (`mmcli` / AT commands) so a dongle can be added later without changing the CLI.

This is not a Telegram phone-ops bot, not iPhone Mirroring, and not the HavenID web hub. It is the terminal/agent handset.

## Install

```powershell
powershell -ExecutionPolicy Bypass -File $env:USERPROFILE\cell\scripts\install.ps1
```

Or run without install:

```powershell
py -3 $env:USERPROFILE\cell\scripts\cell.py --help
```

## Setup

1. Create or reuse a Twilio account (https://www.twilio.com). Trial can own a number and send/receive SMS to **verified** numbers only.
2. Copy Account SID + Auth Token.
3. Init secrets (never commit them):

```powershell
cell init --provider twilio --from-number +1YOURNUMBER
# or import an existing .env that already has TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN
cell init --import-env PATH\to\.env
cell doctor
```

Env overrides files:

| Variable | Role |
|----------|------|
| `TWILIO_ACCOUNT_SID` | Twilio account |
| `TWILIO_AUTH_TOKEN` | Twilio auth token |
| `CELL_FROM` / `TWILIO_PHONE_NUMBER` | Default From |
| `CELL_PROVIDER` | `twilio` (default), `telnyx`, `modem` |
| `TELNYX_API_KEY` | Telnyx bearer key |
| `CELL_HOME` | Override `~/.grok/cell` |
| `CELL_ENV_FILE` | Extra .env path |
| `CELL_AUTO_CONFIRM` | `1` skips `--yes` (dangerous) |
| `CELL_PUBLIC_URL` | Public origin used for Twilio signature checks |

Files:

- `~/.grok/cell/config.toml` - non-secret
- `~/.grok/cell/secrets.toml` - restricted
- `~/.grok/cell/state.sqlite` - inbox cache + daily caps

## Commands

| Command | Purpose |
|---------|---------|
| `cell doctor` | Credentials and API reachability |
| `cell status` | Number, balance, trial flag |
| `cell numbers` | Owned numbers |
| `cell numbers search --area 512` | Find purchasable US locals |
| `cell numbers buy +1... --yes` | Lease a number |
| `cell send +1... "text" --yes` | Outbound SMS |
| `cell inbox [--with +1...]` | Recent messages |
| `cell thread +1...` | One conversation |
| `cell watch` | Poll tail |
| `cell webhook` | Local inbound HTTP server |
| `cell tunnel` | Print cloudflared/ngrok helper |
| `cell numbers webhook https://.../sms` | Pin inbound URL |
| `cell call +1... --say "..." --yes` | Outbound voice |
| `cell mcp` | Stdio MCP |

Every command accepts `--json`.

## Inbound SMS

Two paths:

1. **Poll (default, safest with HavenID).** `cell inbox` and `cell watch` read Twilio's Messages API. Works even if another app owns the number webhook.
2. **Webhook.** `cell webhook` then `cell tunnel`, then `cell numbers webhook https://PUBLIC/sms`. Do not do this on a number HavenID already answers.

## Cost and safety

- US SMS list price (Twilio, 2026): about **$0.0083/segment** plus carrier fees. Local number about **$1.15/month**.
- Send, call, and buy require `--yes` (or a TTY `YES` prompt). Agents must only pass `--yes` after the operator asked to send that message.
- Daily caps default to 20 SMS and 5 calls (`--force` overrides).
- US production SMS needs **A2P 10DLC** (local) or **toll-free verification**. Trial/dev is limited.

Details: `docs/PROVIDERS.md`, `docs/COSTS.md`, `docs/SECURITY.md`.

## Agent / MCP

Grok skill: `~/.grok/skills/cell/SKILL.md`

MCP (after install.ps1, restart Grok Build):

```
cell_status  cell_doctor  cell_numbers  cell_inbox  cell_send  cell_call
```

`cell_send` / `cell_call` require `confirm: true`.
