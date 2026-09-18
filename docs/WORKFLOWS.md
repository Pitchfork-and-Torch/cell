# Agent workflows

## First session (human)

1. `cell init --import-env` or paste SID/token into `~/.grok/cell/secrets.toml`
2. `cell doctor` until provider_api is ok
3. `cell numbers` / `cell numbers search --area NN` / `cell numbers buy +1... --yes`
4. Set `from_number` in config or `CELL_FROM`
5. Send a test to a verified personal mobile: `cell send +1YOU "cell test" --yes`
6. `cell inbox`

## Agent: read texts

```
py -3 $env:USERPROFILE\cell\scripts\cell.py inbox --limit 20 --json
py -3 $env:USERPROFILE\cell\scripts\cell.py thread +15551234567 --json
```

Summarize. Do not forward message bodies to third parties.

## Agent: send a text the operator requested

1. Restate recipient + body + cost note.
2. Only then:

```
py -3 $env:USERPROFILE\cell\scripts\cell.py send +15551234567 "the exact text" --yes --json
```

If the operator did not ask to send, stop.

## Agent: watch during a session

Second terminal: `cell watch`

Or poll `cell inbox --json` every few turns.

## Dedicated number (not HavenID)

```
cell numbers search --area 512
cell numbers buy +1... --yes
cell webhook
cell tunnel
cell numbers webhook https://PUBLIC/sms
```

## Modem later

Set `provider = "modem"` only after `src/cell/providers/modem.py` is implemented. CLI stays the same.
