# Provider research (2026)

Decision: **Twilio is the default**. Telnyx is implemented as a cheaper second backend. USB modem is a stub.

## Comparison

| Provider | Why consider | Why not default | Fit for this CLI |
|----------|--------------|-----------------|------------------|
| **Twilio** | SMS + voice + number search/buy + full Messages list + webhooks + trial. Best docs. Already used on this machine (HavenID). | Higher list price. Trial locks SMS/voice to verified numbers. `<Dial>`/`<Record>` blocked on trial. | **Primary.** Poll inbox works even when another app owns the webhook. |
| **Telnyx** | Owned network. Public 2026 list SMS often ~$0.002-$0.004/part vs Twilio $0.0083. Voice from ~$0.002/min. | New account. Inbox list is profile-oriented, not a simple account dump. Still needs 10DLC. | **Secondary.** Send/numbers/search/buy implemented. Inbox via local webhook. |
| **SignalWire** | Twilio-like APIs, often cheaper. | Extra account. Compatibility quirks. | Future adapter if Twilio price hurts. |
| **Plivo** | Clean API, transparent per-second voice. ~25-40% under Twilio in 2026 writeups. | Another account. Weaker number-inventory UX for a one-number agent. | Future adapter. |
| **Bandwidth** | Carrier-grade. | Enterprise sales motion. Poor hobby/agent onboarding. | Skip. |
| **Vonage / Sinch / Bird** | Fine CPaaS. | No advantage over Twilio/Telnyx for a single-number CLI. | Skip. |
| **USB modem + SIM** | True cellular, not CPaaS. | Hardware, Windows AT-command pain, carrier SMS CAs, no `mmcli` on Windows. | Stub only (`provider = "modem"`). |

Sources checked 2026-08-15: Twilio Messaging API + US SMS pricing, Telnyx Messaging API + pricing, independent 2026 CPaaS comparisons (APIScout, SuprSend, Ringly). Prices change; `cell status` / Twilio console are live truth.

## Why Twilio won for v1

1. This desk already has a Twilio account in the HavenID/SafeDeposit orbit. Reuse beats a second vendor signup for day one.
2. `GET /Messages.json` is the reliable agent inbox. Telnyx does not give that one-call history as cleanly.
3. Voice (`POST /Calls.json` + TwiML `<Say>`) is one request. Enough for "Grok can place a call."
4. Number search/buy is first-class, so the CLI can provision without a browser after credentials exist.
5. Webhook signature validation is well specified.

Telnyx remains the right **cost** upgrade if this number starts sending volume. Switch with `CELL_PROVIDER=telnyx` and `TELNYX_API_KEY`. Same CLI.

## US compliance (not optional)

Anyone sending SMS to US handsets from an application number needs one of:

- **A2P 10DLC** brand + campaign on a local 10-digit number (includes hobbyists on Twilio).
- **Toll-free verification** on a toll-free sender.
- **Short code** (expensive, not for this tool).

Trial/dev can text verified personal numbers. Production to arbitrary US mobiles will be filtered without registration.

## Coexistence with HavenID

HavenID is a web identity + voice hub that may already own the Twilio number webhook. Cell defaults to **polling** so both can share one account.

- Safe: `cell inbox`, `cell watch`, `cell send`, `cell status`
- Unsafe unless intended: `cell numbers webhook` on the HavenID number (replaces inbound TwiML/SMS URL)

Prefer a second Twilio number for a dedicated Grok handset.
