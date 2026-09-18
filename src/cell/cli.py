"""Human + agent CLI: cell <command>."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from typing import Any, Callable

from cell import __version__
from cell import actions
from cell.config import load
from cell.e164 import PhoneError
from cell.models import NeedConfirm, ProviderError
from cell.store import connect, known_sids


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    argv, want_json, want_dry = _peel_global_flags(argv)
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    if want_json:
        args.json = True
    if want_dry:
        args.dry_run = True
    as_json = bool(getattr(args, "json", False))
    fn: Callable[..., Any] | None = getattr(args, "fn", None)
    if fn is None:
        parser.print_help()
        return 2
    try:
        payload = fn(args)
    except NeedConfirm as e:
        return _fail(str(e), as_json, code=2)
    except ProviderError as e:
        return _fail(
            str(e),
            as_json,
            code=1,
            extra={"code": e.code, "status": e.status, "hint": e.hint},
        )
    except PhoneError as e:
        return _fail(str(e), as_json, code=1)
    except (FileNotFoundError, NotImplementedError, OSError, ValueError) as e:
        return _fail(str(e), as_json, code=1)
    except KeyboardInterrupt:
        print("\nstopped", file=sys.stderr)
        return 130
    if payload is None:
        return 0
    if as_json or getattr(args, "force_json", False):
        print(json.dumps(payload, indent=2, ensure_ascii=True))
        return 0 if payload.get("ok", True) else 1
    text = getattr(args, "render", None)
    if callable(text):
        print(text(payload).rstrip())
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0 if payload.get("ok", True) else 1


def _peel_global_flags(argv: list[str]) -> tuple[list[str], bool, bool]:
    """Accept --json / --dry-run before or after the subcommand.

    argparse subparsers with the same flags would otherwise overwrite a
    top-level --json with the subparser default (False).
    """
    json_flag = False
    dry_flag = False
    kept: list[str] = []
    for arg in argv:
        if arg == "--json":
            json_flag = True
            continue
        if arg == "--dry-run":
            dry_flag = True
            continue
        kept.append(arg)
    return kept, json_flag, dry_flag


def _positive_int(value: str) -> int:
    try:
        n = int(value)
    except ValueError as e:
        raise argparse.ArgumentTypeError("not an integer") from e
    if n < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return n


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine-readable JSON")
    common.add_argument(
        "--dry-run",
        action="store_true",
        help="validate only; do not call the carrier or spend money",
    )

    p = argparse.ArgumentParser(
        prog="cell",
        description="Own and use a real phone number from the terminal (SMS first, voice second).",
        parents=[common],
        epilog="Costly actions (send, call, buy, numbers webhook) need --yes. Preview with --dry-run.",
    )
    p.add_argument("--version", action="version", version=f"cell {__version__}")
    sub = p.add_subparsers(dest="cmd")

    def add_cmd(name: str, help_text: str) -> argparse.ArgumentParser:
        return sub.add_parser(name, help=help_text, parents=[common])

    s = add_cmd("status", "number, balance, connection")
    s.set_defaults(fn=lambda a: actions.status(), render=_render_status)

    s = add_cmd("doctor", "config and credential diagnostics")
    s.add_argument("--offline", action="store_true", help="skip provider API (no network)")
    s.set_defaults(
        fn=lambda a: actions.doctor(live=not (a.offline or a.dry_run)),
        render=_render_doctor,
    )

    s = add_cmd("init", "write ~/.grok/cell config + secrets (masked)")
    s.add_argument("--provider", default="twilio", choices=["twilio", "telnyx", "modem"])
    s.add_argument("--from-number", default="", dest="from_number")
    s.add_argument("--import-env", default="", help="path to .env with TWILIO_* or TELNYX_*")
    s.set_defaults(
        fn=lambda a: actions.init(provider=a.provider, from_number=a.from_number, import_env=a.import_env or None),
        render=_render_init,
    )

    n = add_cmd("numbers", "owned numbers, search, buy, webhook pin")
    nset = n.add_subparsers(dest="ncmd")
    n.set_defaults(fn=lambda a: actions.numbers(), render=_render_numbers)
    ns = nset.add_parser("search", help="search purchasable numbers", parents=[common])
    ns.add_argument("--country", default="")
    ns.add_argument("--area", default="", help="US area code")
    ns.add_argument("--limit", type=_positive_int, default=8)
    ns.set_defaults(
        fn=lambda a: actions.search_numbers(country=a.country or None, area=a.area or None, limit=a.limit),
        render=_render_search,
    )
    nb = nset.add_parser("buy", help="purchase a number (costs monthly rent)", parents=[common])
    nb.add_argument("number")
    nb.add_argument("--yes", action="store_true")
    nb.set_defaults(
        fn=lambda a: actions.buy_number(a.number, yes=a.yes, dry_run=a.dry_run),
        render=_render_buy,
    )
    nw = nset.add_parser("webhook", help="pin inbound SMS URL on a number", parents=[common])
    nw.add_argument("url")
    nw.add_argument("--number", default="")
    nw.add_argument("--yes", action="store_true")
    nw.set_defaults(
        fn=lambda a: actions.set_webhook(a.url, number=a.number or None, yes=a.yes, dry_run=a.dry_run),
        render=_render_webhook,
    )

    s = add_cmd("send", "send SMS")
    s.add_argument("to")
    s.add_argument("message", nargs="+")
    s.add_argument("--yes", action="store_true")
    s.add_argument("--force", action="store_true", help="ignore daily SMS cap")
    s.set_defaults(
        fn=lambda a: actions.send_sms(a.to, " ".join(a.message), yes=a.yes, force=a.force, dry_run=a.dry_run),
        render=_render_send,
    )

    s = add_cmd("inbox", "recent messages")
    s.add_argument("--limit", type=_positive_int, default=20)
    s.add_argument("--with", dest="with_n", default="")
    s.add_argument("--local", action="store_true", help="read sqlite cache only (no carrier)")
    s.set_defaults(
        fn=lambda a: actions.inbox(limit=a.limit, with_n=a.with_n or None, local=bool(a.local or a.dry_run)),
        render=_render_inbox,
    )

    s = add_cmd("thread", "conversation with one number")
    s.add_argument("number")
    s.add_argument("--limit", type=_positive_int, default=40)
    s.add_argument("--local", action="store_true", help="read sqlite cache only (no carrier)")
    s.set_defaults(
        fn=lambda a: actions.thread(a.number, limit=a.limit, local=bool(a.local or a.dry_run)),
        render=_render_inbox,
    )

    s = add_cmd("watch", "tail inbound SMS (poll provider + local store)")
    s.add_argument("--interval", type=float, default=3.0)
    s.add_argument("--limit", type=_positive_int, default=20)
    s.add_argument("--once", action="store_true", help="poll once and exit (no long-running loop)")
    s.add_argument("--local", action="store_true", help="read sqlite cache only (no carrier)")
    s.set_defaults(fn=_watch, render=_render_inbox)

    s = add_cmd("webhook", "run local inbound HTTP server")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=0)
    s.set_defaults(fn=_webhook)

    s = add_cmd("tunnel", "print cloudflared/ngrok helper for the webhook")
    s.add_argument("--port", type=int, default=0)
    s.set_defaults(fn=_tunnel, render=lambda d: d.get("text") or json.dumps(d, indent=2))

    s = add_cmd("call", "outbound voice call (speaks --say)")
    s.add_argument("to")
    s.add_argument("--say", default="This is Grok calling from the cell tool. Goodbye.")
    s.add_argument("--url", default="", help="TwiML URL instead of --say")
    s.add_argument("--yes", action="store_true")
    s.add_argument("--force", action="store_true")
    s.set_defaults(
        fn=lambda a: actions.call(a.to, say=a.say, url=a.url or None, yes=a.yes, force=a.force, dry_run=a.dry_run),
        render=_render_call,
    )

    s = add_cmd("mcp", "stdio MCP server for Grok Build")
    s.set_defaults(fn=_mcp)

    return p


def _watch(args: argparse.Namespace) -> dict | None:
    local = bool(getattr(args, "local", False) or getattr(args, "dry_run", False))
    if getattr(args, "once", False):
        return actions.inbox(limit=args.limit, local=local)
    cfg = load()
    con = connect(cfg.db_path)
    seen = known_sids(con)
    print(f"watching every {args.interval}s (Ctrl+C to stop)")
    try:
        while True:
            try:
                batch = actions.inbox(limit=args.limit, cfg=cfg, local=local)
                msgs = batch.get("messages") or []
            except (ProviderError, NotImplementedError) as e:
                print(f"[warn] {e}", file=sys.stderr)
                msgs = []
            for item in reversed(msgs):
                sid = item.get("sid") or ""
                if not sid or sid in seen:
                    continue
                seen.add(sid)
                direction = item.get("direction") or "?"
                stamp = item.get("created") or "now"
                print(f"{stamp}  {direction:8}  {item.get('from_n')} -> {item.get('to')}  {item.get('body')}")
            time.sleep(max(1.0, float(args.interval)))
    finally:
        con.close()
    return None


def _webhook(args: argparse.Namespace) -> dict | None:
    from cell.webhook import serve

    cfg = load()
    port = args.port or cfg.webhook_port
    serve(cfg, host=args.host, port=port)
    return None


def _tunnel(args: argparse.Namespace) -> dict:
    cfg = load()
    port = args.port or cfg.webhook_port
    cf = shutil.which("cloudflared")
    ng = shutil.which("ngrok")
    lines = [
        f"Local webhook: http://127.0.0.1:{port}/sms",
        "Start the webhook in another terminal:  cell webhook",
        "",
    ]
    if cf:
        lines.append("Found cloudflared. Run:")
        lines.append(f"  {cf} tunnel --url http://127.0.0.1:{port}")
    else:
        lines.append("cloudflared not on PATH. Install Cloudflare Tunnel, then:")
        lines.append(f"  cloudflared tunnel --url http://127.0.0.1:{port}")
    if ng:
        lines.append(f"Or ngrok: {ng} http {port}")
    lines.extend(
        [
            "",
            "Then pin the public https URL:",
            "  cell numbers webhook https://YOUR-TUNNEL/sms --yes",
            "",
            "If HavenID already owns this number's SMS webhook, skip pin and use: cell inbox / cell watch (Twilio poll).",
        ]
    )
    return {"ok": True, "port": port, "cloudflared": bool(cf), "ngrok": bool(ng), "text": "\n".join(lines)}


def _mcp(_args: argparse.Namespace) -> dict | None:
    from cell.mcp_server import main as mcp_main

    raise SystemExit(mcp_main())


def _render_status(d: dict) -> str:
    if not d.get("ok"):
        return f"cell: {d.get('error')}\nconfig: {d.get('config')}"
    lines = [
        f"cell {d.get('version')}  provider={d.get('provider')}  from={d.get('from_number') or '-'}",
        f"account: {d.get('account')}  status={d.get('account_status')}  type={d.get('account_type')}",
    ]
    if d.get("balance") is not None:
        lines.append(f"balance: {d.get('balance')} {d.get('currency') or ''}".rstrip())
    usage = d.get("usage_today") or {}
    lines.append(f"today: sms={usage.get('sms', 0)}  calls={usage.get('call', 0)}")
    if d.get("trial"):
        lines.append("trial: SMS and calls only to verified numbers until you upgrade.")
    nums = d.get("numbers") or []
    if nums:
        lines.append("numbers:")
        for n in nums:
            caps = []
            if n.get("sms"):
                caps.append("sms")
            if n.get("voice"):
                caps.append("voice")
            if n.get("mms"):
                caps.append("mms")
            mark = " (default)" if n.get("e164") == d.get("from_number") else ""
            lines.append(f"  {n.get('e164')}  {','.join(caps) or '-'}{mark}")
    return "\n".join(lines)


def _render_doctor(d: dict) -> str:
    tag = "OK" if d.get("ok") else "FIX"
    if d.get("offline"):
        tag = f"{tag} (offline)"
    lines = [f"cell doctor  {tag}"]
    for c in d.get("checks") or []:
        mark = "ok" if c.get("ok") else "FAIL"
        lines.append(f"  [{mark}] {c.get('name')}: {c.get('detail')}")
    return "\n".join(lines)


def _render_init(d: dict) -> str:
    return (
        f"wrote {d.get('config')}\n"
        f"wrote {d.get('secrets')} (restricted)\n"
        f"provider={d.get('provider')} from={d.get('from_number') or '-'}\n"
        f"next: cell doctor"
    )


def _render_numbers(d: dict) -> str:
    nums = d.get("numbers") or []
    if not nums:
        return "no numbers on this account. Try: cell numbers search --area 512"
    lines = [f"from={d.get('from_number') or '-'}"]
    for n in nums:
        hook = (n.get("extra") or {}).get("sms_url") or ""
        hook_s = f"  sms_url={hook}" if hook else ""
        lines.append(f"{n.get('e164')}  sms={n.get('sms')} voice={n.get('voice')}{hook_s}")
    return "\n".join(lines)


def _render_search(d: dict) -> str:
    nums = d.get("numbers") or []
    if not nums:
        return "no available numbers for that query"
    lines = [d.get("cost") or ""]
    for n in nums:
        extra = n.get("extra") or {}
        where = " ".join(x for x in (extra.get("locality"), extra.get("region")) if x)
        lines.append(f"{n.get('e164')}  {where}".rstrip())
    lines.append("buy: cell numbers buy +1... --yes")
    return "\n".join(x for x in lines if x)


def _render_buy(d: dict) -> str:
    if d.get("dry_run"):
        return f"DRY-RUN buy {d.get('number')}\n{d.get('cost') or ''}".rstrip()
    n = (d.get("number") or {}).get("e164")
    return f"purchased {n}\nset as default: add from_number to ~/.grok/cell/config.toml or CELL_FROM"


def _render_send(d: dict) -> str:
    if d.get("dry_run"):
        lines = [
            f"DRY-RUN send {d.get('from_n')} -> {d.get('to')}",
            d.get("cost") or "",
        ]
        if d.get("would_block_rate"):
            lines.append("would hit daily SMS cap (pass --force to override on a real send)")
        return "\n".join(x for x in lines if x)
    m = d.get("message") or {}
    return f"sent {m.get('sid')}  {m.get('from_n')} -> {m.get('to')}  status={m.get('status')}\n{d.get('cost')}"


def _render_inbox(d: dict) -> str:
    msgs = d.get("messages") or []
    if not msgs:
        extra = f"inbox empty (source={d.get('source')})"
        if d.get("provider_error"):
            extra += f"\nprovider: {d.get('provider_error')}"
        return extra
    lines = [f"inbox source={d.get('source')}  {len(msgs)} message(s)"]
    if d.get("provider_error"):
        lines.append(f"provider: {d.get('provider_error')}")
    for m in msgs:
        body = (m.get("body") or "").replace("\n", " ")
        if len(body) > 160:
            body = body[:157] + "..."
        lines.append(
            f"{m.get('created') or '-':<28} {(m.get('direction') or '?'):8} {m.get('from_n')} -> {m.get('to')}  {body}"
        )
    return "\n".join(lines)


def _render_call(d: dict) -> str:
    if d.get("dry_run"):
        lines = [
            f"DRY-RUN call {d.get('from_n')} -> {d.get('to')}",
            d.get("cost") or "",
        ]
        if d.get("would_block_rate"):
            lines.append("would hit daily call cap (pass --force to override on a real call)")
        return "\n".join(x for x in lines if x)
    c = d.get("call") or {}
    return f"call {c.get('sid')}  {c.get('from_n')} -> {c.get('to')}  status={c.get('status')}\n{d.get('cost')}"


def _render_webhook(d: dict) -> str:
    if d.get("dry_run"):
        return f"DRY-RUN pin {d.get('url')} on {d.get('number') or '-'}\n{d.get('warning') or ''}".rstrip()
    return d.get("sms_url") or d.get("note") or json.dumps(d, indent=2)


def _fail(msg: str, as_json: bool, code: int, extra: dict | None = None) -> int:
    if as_json:
        payload: dict[str, Any] = {"ok": False, "error": msg}
        if extra:
            for key, val in extra.items():
                if val is not None:
                    payload[key] = val
        print(json.dumps(payload, ensure_ascii=True))
    else:
        print(f"cell: {msg}", file=sys.stderr)
        hint = extra.get("hint") if extra else None
        if hint and hint not in msg:
            print(f"hint: {hint}", file=sys.stderr)
    return code
