# Costs (Twilio US list, 2026-08-15)

Approximate. Carrier fees extra. Confirm in the Twilio console.

| Item | About |
|------|--------|
| Local number rent | $1.15 / month |
| Toll-free rent | $2.15 / month |
| SMS in or out (long code / TF / short code) | $0.0083 / segment |
| MMS out | $0.022 |
| Carrier fee (AT&T SMS out example) | $0.0035 / segment |
| Failed message processing | $0.001 |
| Voice outbound (typical US) | about $0.014 / min (see Voice pricing) |
| 10DLC / TFV registration | one-time + recurring carrier fees |

Telnyx public messaging pages quote roughly $0.002-$0.004 per SMS part on-net. Still plus 10DLC.

## Caps in this tool

`~/.grok/cell/config.toml`:

```
daily_sms_limit = 20
daily_call_limit = 5
auto_confirm = false
```

`--force` bypasses the daily cap. `--yes` is still required for send/call/buy unless `CELL_AUTO_CONFIRM=1`.
