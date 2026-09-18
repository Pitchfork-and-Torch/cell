# Agent workflows

## First session (human)

1. `cell init --import-env` or paste SID/token into `~/.grok/cell/secrets.toml`
2. `cell doctor --offline` then `cell doctor` until provider_api is ok
3. `cell numbers` / `cell numbers search --area NN` / `cell numbers buy +1... --dry-run` / `cell numbers buy +1... --yes`
4. Set `from_number` in config or `CELL_FROM`
5. Preview: `cell send +1YOU "cell test" --dry-run`
6. Send a test to a verified personal mobile: `cell send +1YOU "cell test" --yes`
7. `cell inbox` or `cell inbox --local`

## Agent: read texts

```
py -3 $env:USERPROFILE\cell\scripts\cell.py inbox --limit 20 --json
py -3 $env:USERPROFILE\cell\scripts\cell.py inbox --local --json
py -3 $env:USERPROFILE\cell\scripts\cell.py thread +15551234567 --json
```

Summarize. Do not forward message bodies to third parties.

## Agent: send a text the operator requested

1. Restate recipient + body + cost note.
2. Preview (no carrier):

```
py -3 $env:USERPROFILE\cell\scripts\cell.py send +15551234567 "the exact text" --dry-run --json
```

3. Only if the operator asked to send that exact text, then:

```
py -3 $env:USERPROFILE\cell\scripts\cell.py send +15551234567 "the exact text" --yes --json
```

If the operator did not ask to send, stop. `--dry-run` does not need `--yes` and does not hit the carrier.

## Agent: watch during a session

Prefer a single poll (does not hang the TUI):

```
py -3 $env:USERPROFILE\cell\scripts\cell.py watch --once --json
py -3 $env:USERPROFILE\cell\scripts\cell.py inbox --local --json
```

Long-running `cell watch` belongs in a second terminal, not inside Grok Build.

## Dry-run / offline / local (no carrier)

```
cell doctor --offline --json
cell send +15551234567 "body" --dry-run --json
cell call +15551234567 --say "hi" --dry-run --json
cell numbers buy +15551234567 --dry-run --json
cell numbers webhook https://example.com/sms --dry-run --json
cell inbox --local --json
cell watch --once --local --json
```

`--dry-run` on send/call/buy/webhook validates and prints the action. It does not spend money and does not change the live number.

## Dedicated number (not HavenID)

```
cell numbers search --area 512
cell numbers buy +1... --yes
cell webhook
cell tunnel
cell numbers webhook https://PUBLIC/sms --yes
```

## Modem later

Set `provider = "modem"` only after `src/cell/providers/modem.py` is implemented. CLI stays the same.
