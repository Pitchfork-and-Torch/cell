"""Shared operations for CLI and MCP."""

from __future__ import annotations

from typing import Any

from cell import __version__
from cell.config import Config, data_dir, load, write_init
from cell.confirm import buy_cost_note, call_cost_note, require_yes, segments, sms_cost_note
from cell.e164 import PhoneError, normalize
from cell.errors import hint_for
from cell.models import ProviderError
from cell.providers import get_provider
from cell.store import bump_usage, connect, list_local, upsert_message, usage_today


def _clamp_limit(limit: int, *, default: int = 20, max_n: int = 100) -> int:
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = default
    return max(1, min(n, max_n))


def status(cfg: Config | None = None) -> dict[str, Any]:
    cfg = cfg or load()
    try:
        provider = get_provider(cfg)
        data = provider.status()
    except ProviderError as e:
        return {
            "ok": False,
            "version": __version__,
            "config": cfg.masked(),
            "error": str(e),
            "code": e.code,
            "hint": e.hint,
        }
    usage = _usage(cfg)
    return {
        "ok": True,
        "version": __version__,
        "config": cfg.masked(),
        "usage_today": usage,
        **data,
    }


def doctor(cfg: Config | None = None, *, live: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    if cfg is None:
        home = data_dir()
        add("data_dir", home.is_dir(), str(home))
        cfg = load(create=True)
    else:
        add("data_dir", cfg.home.is_dir(), str(cfg.home))

    add("config_file", cfg.config_path.is_file(), str(cfg.config_path))
    add("secrets_file", cfg.secrets_path.is_file(), str(cfg.secrets_path))

    try:
        con = connect(cfg.db_path)
        con.execute("SELECT 1")
        con.close()
        add("sqlite", True, "writable")
    except OSError as e:
        add("sqlite", False, str(e))

    add("daily_sms_limit", cfg.daily_sms_limit > 0, str(cfg.daily_sms_limit))
    add("daily_call_limit", cfg.daily_call_limit > 0, str(cfg.daily_call_limit))
    add(
        "auto_confirm",
        not cfg.auto_confirm,
        "off" if not cfg.auto_confirm else "ON (dangerous: skips --yes)",
    )

    if cfg.provider == "twilio":
        sid = cfg.twilio_account_sid or ""
        if not sid:
            add("twilio_sid", False, "missing")
        elif not sid.startswith("AC"):
            add("twilio_sid", False, "should start with AC")
        else:
            add("twilio_sid", True, "AC... present")
        add("twilio_token", bool(cfg.twilio_auth_token), "set" if cfg.twilio_auth_token else "missing")
    elif cfg.provider == "telnyx":
        add("telnyx_key", bool(cfg.telnyx_api_key), "set" if cfg.telnyx_api_key else "missing")
    elif cfg.provider in ("modem", "mmcli", "usb"):
        add("modem", False, "stub only - use twilio or telnyx")
    elif cfg.provider == "fake":
        add(
            "fake_provider",
            False,
            "CELL_PROVIDER=fake (no carrier). Unset CELL_PROVIDER and CELL_FAKE for production.",
        )
    else:
        add("provider", False, f"unknown provider: {cfg.provider}")

    if cfg.from_number:
        try:
            normalize(cfg.from_number)
            add("from_number", True, cfg.from_number)
        except PhoneError as e:
            add("from_number", False, str(e))
    else:
        add("from_number", False, "not set (cell init or CELL_FROM)")

    probed: dict[str, Any] = {}
    if not live:
        add("provider_api", True, "skipped (offline)")
    else:
        try:
            probed = get_provider(cfg).status()
            add("provider_api", True, f"{cfg.provider} reachable")
            nums = probed.get("numbers") or []
            add("owned_numbers", bool(nums), f"{len(nums)} number(s)")
            if probed.get("trial"):
                add(
                    "trial",
                    True,
                    "Twilio trial: SMS/calls only to verified numbers. Upgrade for real PSTN.",
                )
            if cfg.from_number and nums:
                try:
                    want = normalize(cfg.from_number)
                except PhoneError:
                    want = cfg.from_number
                owned = {n.get("e164") for n in nums if isinstance(n, dict)}
                add(
                    "from_owned",
                    want in owned,
                    "from_number is on the account" if want in owned else "from_number is not on this account",
                )
        except ProviderError as e:
            detail = str(e)
            h = e.hint or hint_for(e.code)
            if h and h not in detail:
                detail = f"{detail} Hint: {h}"
            add("provider_api", False, detail)

    skip_ok = {"trial"}
    return {
        "ok": all(c["ok"] for c in checks if c["name"] not in skip_ok),
        "version": __version__,
        "checks": checks,
        "offline": not live,
        "usage_today": _usage(cfg),
        "live": {
            k: probed.get(k)
            for k in ("provider", "balance", "currency", "account_status", "trial", "from_number")
            if probed
        },
    }


def init(
    *,
    provider: str = "twilio",
    from_number: str = "",
    import_env: str | None = None,
) -> dict[str, Any]:
    from pathlib import Path

    cfg = write_init(
        provider=provider,
        from_number=from_number,
        import_env=Path(import_env) if import_env else None,
    )
    return {
        "ok": True,
        "home": str(cfg.home),
        "config": str(cfg.config_path),
        "secrets": str(cfg.secrets_path),
        "provider": cfg.provider,
        "from_number": cfg.from_number or None,
        "twilio_account_sid": cfg.masked()["twilio_account_sid"],
        "twilio_auth_token": cfg.masked()["twilio_auth_token"],
        "telnyx_api_key": cfg.masked()["telnyx_api_key"],
    }


def numbers(cfg: Config | None = None) -> dict[str, Any]:
    cfg = cfg or load()
    owned = get_provider(cfg).list_owned_numbers()
    return {
        "ok": True,
        "from_number": cfg.from_number or None,
        "numbers": [n.to_dict() for n in owned],
    }


def search_numbers(
    *,
    country: str | None = None,
    area: str | None = None,
    limit: int = 8,
    cfg: Config | None = None,
) -> dict[str, Any]:
    cfg = cfg or load()
    found = get_provider(cfg).search_numbers(
        country=country or cfg.country or "US",
        area_code=area,
        limit=_clamp_limit(limit, default=8, max_n=20),
    )
    return {"ok": True, "numbers": [n.to_dict() for n in found], "cost": buy_cost_note()}


def buy_number(
    e164: str,
    *,
    yes: bool = False,
    dry_run: bool = False,
    cfg: Config | None = None,
) -> dict[str, Any]:
    cfg = cfg or load()
    n = normalize(e164)
    cost = buy_cost_note()
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "would": "buy_number",
            "number": n,
            "cost": cost,
        }
    require_yes(yes=yes, auto=cfg.auto_confirm, what=f"Buy {n}?", note=cost)
    bought = get_provider(cfg).buy_number(n)
    return {"ok": True, "dry_run": False, "number": bought.to_dict()}


def send_sms(
    to: str,
    body: str,
    *,
    yes: bool = False,
    force: bool = False,
    dry_run: bool = False,
    cfg: Config | None = None,
) -> dict[str, Any]:
    cfg = cfg or load()
    dest = normalize(to)
    if not (body or "").strip():
        raise ProviderError("empty SMS body")
    if not (cfg.from_number or "").strip():
        raise ProviderError("from_number not set. Run cell init --from-number +1... or set CELL_FROM.")
    src = normalize(cfg.from_number)
    cost = sms_cost_note(body)
    usage = _usage(cfg)
    at_cap = usage.get("sms", 0) >= cfg.daily_sms_limit and not force
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "would": "send_sms",
            "from_n": src,
            "to": dest,
            "body": body,
            "segments": segments(body),
            "cost": cost,
            "usage_today": usage,
            "daily_limit": cfg.daily_sms_limit,
            "would_block_rate": at_cap,
            "would_succeed": not at_cap,
        }
    require_yes(
        yes=yes,
        auto=cfg.auto_confirm,
        what=f"Send SMS to {dest}?",
        note=cost,
    )
    _rate_guard(cfg, "sms", cfg.daily_sms_limit, force)
    msg = get_provider(cfg).send_sms(dest, body)
    _rate_commit(cfg, "sms")
    con = connect(cfg.db_path)
    try:
        upsert_message(con, msg, source="outbound")
    finally:
        con.close()
    return {"ok": True, "dry_run": False, "message": msg.to_dict(), "cost": cost}


def inbox(
    *,
    limit: int = 20,
    with_n: str | None = None,
    local: bool = False,
    cfg: Config | None = None,
) -> dict[str, Any]:
    cfg = cfg or load()
    limit = _clamp_limit(limit)
    peer = normalize(with_n) if with_n else None
    if local:
        con = connect(cfg.db_path)
        try:
            messages = list_local(con, limit=limit, with_n=peer)
        finally:
            con.close()
        return {
            "ok": True,
            "source": "local",
            "provider_error": None,
            "messages": [m.to_dict() for m in messages],
        }
    messages = []
    source = "provider"
    provider_error = None
    try:
        messages = get_provider(cfg).list_messages(limit=limit, with_n=peer)
        con = connect(cfg.db_path)
        try:
            for m in messages:
                upsert_message(con, m, source="provider")
        finally:
            con.close()
    except (ProviderError, NotImplementedError) as e:
        source = "local"
        provider_error = str(e)
        con = connect(cfg.db_path)
        try:
            messages = list_local(con, limit=limit, with_n=peer)
        finally:
            con.close()
    return {
        "ok": True,
        "source": source,
        "provider_error": provider_error,
        "messages": [m.to_dict() for m in messages],
    }


def thread(
    with_n: str,
    *,
    limit: int = 40,
    local: bool = False,
    cfg: Config | None = None,
) -> dict[str, Any]:
    return inbox(limit=limit, with_n=with_n, local=local, cfg=cfg)


def call(
    to: str,
    *,
    say: str | None = None,
    url: str | None = None,
    yes: bool = False,
    force: bool = False,
    dry_run: bool = False,
    cfg: Config | None = None,
) -> dict[str, Any]:
    cfg = cfg or load()
    dest = normalize(to)
    if not (cfg.from_number or "").strip():
        raise ProviderError("from_number not set. Run cell init --from-number +1... or set CELL_FROM.")
    src = normalize(cfg.from_number)
    cost = call_cost_note()
    usage = _usage(cfg)
    at_cap = usage.get("call", 0) >= cfg.daily_call_limit and not force
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "would": "place_call",
            "from_n": src,
            "to": dest,
            "say": say,
            "url": url,
            "cost": cost,
            "usage_today": usage,
            "daily_limit": cfg.daily_call_limit,
            "would_block_rate": at_cap,
            "would_succeed": not at_cap,
        }
    require_yes(yes=yes, auto=cfg.auto_confirm, what=f"Place voice call to {dest}?", note=cost)
    _rate_guard(cfg, "call", cfg.daily_call_limit, force)
    result = get_provider(cfg).place_call(dest, say=say, twiml_url=url)
    _rate_commit(cfg, "call")
    return {"ok": True, "dry_run": False, "call": result.to_dict(), "cost": cost}


def set_webhook(
    url: str,
    *,
    number: str | None = None,
    yes: bool = False,
    dry_run: bool = False,
    cfg: Config | None = None,
) -> dict[str, Any]:
    cfg = cfg or load()
    if not url.startswith("https://") and not url.startswith("http://"):
        raise ProviderError("webhook URL must be http(s)")
    target = number or cfg.from_number
    if target:
        target = normalize(target)
    note = (
        "This replaces the previous SMS webhook on this number. "
        "Do not point a HavenID number here unless you intend to take inbound away from HavenID."
    )
    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "would": "set_webhook",
            "url": url,
            "number": target,
            "warning": note,
        }
    require_yes(
        yes=yes,
        auto=cfg.auto_confirm,
        what=f"Pin SMS webhook {url} on {target or 'default number'}?",
        note=note,
    )
    data = get_provider(cfg).set_sms_webhook(url, number)
    return {"ok": True, "dry_run": False, **data}


def _rate_guard(cfg: Config, kind: str, limit: int, force: bool) -> None:
    con = connect(cfg.db_path)
    try:
        used = usage_today(con, kind)
    finally:
        con.close()
    if used >= limit and not force:
        raise ProviderError(
            f"daily {kind} limit reached ({used}/{limit}). Pass --force to override, or raise daily_{kind}_limit in config."
        )


def _rate_commit(cfg: Config, kind: str) -> None:
    con = connect(cfg.db_path)
    try:
        bump_usage(con, kind)
    finally:
        con.close()


def _usage(cfg: Config) -> dict[str, int]:
    con = connect(cfg.db_path)
    try:
        data = {"sms": usage_today(con, "sms"), "call": usage_today(con, "call")}
    finally:
        con.close()
    return data
