# Security

- Secrets live in `~/.grok/cell/secrets.toml` (user-only ACL when the OS allows) or environment variables.
- Never put SIDs/tokens in the skill body, git, Telegram, or commit messages.
- `cell` never prints the auth token. `doctor` / `status` mask the SID.
- Twilio inbound webhooks are signature-checked when a token is configured. Set `CELL_PUBLIC_URL` to the public https origin so the signed URL matches (tunnels rewrite Host).
- The webhook does **not** auto-reply. Auto-reply is an easy SMS loop and a cost bomb.
- Send/call/buy/`numbers webhook` are gated. Agents must not pass `--yes` / `confirm: true` unless the operator asked for that exact action.
- `--dry-run`, `doctor --offline`, and `inbox --local` never call the carrier. Use them in tests and for previews.
- `CELL_PROVIDER=fake` plus `CELL_FAKE=1` is test-only. `cell doctor` fails closed while fake is set.
- Do not enable `auto_confirm` except on a locked-down throwaway account. `cell doctor` reports FIX if it is on.
- Treat the number as a public identity. Do not text secrets. Do not use it for 2FA of high-value accounts if the webhook or Twilio console can be read by more than the operator.
