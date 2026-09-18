# cell

**Give an agent a real phone number.** SMS first, voice second. No handset required.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-0.1.0-informational)](pyproject.toml)

A small CLI (plus optional MCP) that owns a PSTN number from the terminal. Default backend is **Twilio**. **Telnyx** is a cheaper second path. A USB-modem stub is reserved so a dongle can land later without changing commands.

This is not iPhone Mirroring, not a Telegram ops bot, and not the [HavenID](https://github.com/Pitchfork-and-Torch/HavenID) web hub. It is the agent handset.

```
cell status
cell send +15551234567 "hello" --yes
cell inbox --limit 20
cell watch
cell call +15551234567 --say "This is Grok." --yes
```

## Install

```powershell
git clone https://github.com/Pitchfork-and-Torch/cell.git
cd cell
py -3 -m pip install -e .
cell --help
```

Windows shim (`cell` on PATH) plus optional Grok MCP stanza:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install.ps1
```

Run without install:

```powershell
py -3 .\scripts\cell.py --help
```

## Setup

1. Create or reuse a Twilio account. Trial can own a number and SMS **verified** destinations only.
2. Copy Account SID + Auth Token. Never commit them.
3. Init secrets:

```powershell
cell init --provider twilio --from-number +1YOURNUMBER
# or import an existing .env that already has TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN
cell init --import-env PATH\to\.env
cell doctor
```

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

Files (not in git):

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

Buy, send, and call are gated. Pass `--yes` only for the action you meant.

## Docs

- [Security](docs/SECURITY.md)
- [Providers](docs/PROVIDERS.md)
- [Costs](docs/COSTS.md)
- [Workflows](docs/WORKFLOWS.md)
- [Modem stub](docs/MODEM.md)

## Related

| Tool | Role |
|------|------|
| [HavenID](https://github.com/Pitchfork-and-Torch/HavenID) | Self-hosted screening-number web hub |
| [phone-harness](https://github.com/Pitchfork-and-Torch/phone-harness) | Drive a real iPhone through macOS iPhone Mirroring |
| [grok-orbit](https://github.com/Pitchfork-and-Torch/grok-orbit) | Desktop command center for Grok CLI and Bot |

## License

MIT. See [LICENSE](LICENSE). Issues on this repo only.
