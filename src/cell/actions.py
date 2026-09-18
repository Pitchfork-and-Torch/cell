"""Shared operations for CLI and MCP."""

from __future__ import annotations

from typing import Any

from cell import __version__
from cell.config import Config, load, write_init
from cell.confirm import buy_cost_note, call_cost_note, require_yes, sms_cost_note
from cell.e164 import PhoneError, normalize
from cell.models import NeedConfirm, ProviderError
from cell.providers import get_provider
from cell.store import bump_usage, connect, list_local, upsert_message, usage_today


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
        }
    usage = _usage(cfg)
    return {
        "ok": True,
        "version": __version__,
        "config": cfg.masked(),
        "usage_today": usage,
        **data,
    }


def doctor(cfg: Config | None = None) -> dict[str, Any]:
    cfg = cfg or load()
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": ok, "detail": detail})

    add("data_dir", cfg.home.is_dir(), str(cfg.home))
    add("config_file", cfg.config_path.is_file(), str(cfg.config_path))
    add("secrets_file", cfg.secrets_path.is_file(), str(cfg.secrets_path))
    if cfg.provider == "twilio":
        add("twilio_sid", cfg.twilio_account_sid.startswith("AC"), "AC... present" if cfg.twilio_account_sid else "missing")
        add("twilio_token", bool(cfg.twilio_auth_token), "set" if cfg.twilio_auth_token else "missing")
    elif cfg.provider == "telnyx":
        add("telnyx_key", bool(cfg.telnyx_api_key), "set" if cfg.telnyx_api_key else "missing")
    elif cfg.provider in ("modem", "mmcli", "usb"):
        add("modem", False, "stub only - use twilio or telnyx")
    if cfg.from_number:
        try:
            normalize(cfg.from_number)
            add("from_number", True, cfg.from_number)
        except PhoneError as e:
            add("from_number", False, str(e))
    else:
        add("from_number", False, "not set (cell init or CELL_FROM)")
    live: dict[str, Any] = {}
    try:
        live = get_provider(cfg).status()
        add("provider_api", True, f"{cfg.provider} reachable")
        nums = live.get("numbers") or []
        add("owned_numbers", bool(nums), f"{len(nums)} number(s)")
        if live.get("trial"):
            add(
                "trial",
                True,
                "Twilio trial: SMS/calls only to verified numbers. Upgrade for real PSTN.",
            )
    except ProviderError as e:
        add("provider_api", False, str(e))
    return {
        "ok": all(c["ok"] for c in checks if c["name"] not in ("trial",)),
        "version": __version__,
        "checks": checks,
        "live": {k: live.get(k) for k in ("provider", "balance", "currency", "account_status", "trial", "from_number") if live},
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
        limit=limit,
    )
    return {"ok": True, "numbers": [n.to_dict() for n in found], "cost": buy_cost_note()}


def buy_number(e164: str, *, yes: bool = False, cfg: Config | None = None) -> dict[str, Any]:
    cfg = cfg or load()
    n = normalize(e164)
    require_yes(yes=yes, auto=cfg.auto_confirm, what=f"Buy {n}?", note=buy_cost_note())
    bought = get_provider(cfg).buy_number(n)
    return {"ok": True, "number": bought.to_dict()}


def send_sms(
    to: str,
    body: str,
    *,
    yes: bool = False,
    force: bool = False,
    cfg: Config | None = None,
) -> dict[str, Any]:
    cfg = cfg or load()
    dest = normalize(to)
    if not (body or "").strip():
        raise ProviderError("empty SMS body")
    require_yes(
        yes=yes,
        auto=cfg.auto_confirm,
        what=f"Send SMS to {dest}?",
        note=sms_cost_note(body),
    )
    _rate(cfg, "sms", cfg.daily_sms_limit, force)
    msg = get_provider(cfg).send_sms(dest, body)
    con = connect(cfg.db_path)
    upsert_message(con, msg, source="outbound")
    con.close()
    return {"ok": True, "message": msg.to_dict(), "cost": sms_cost_note(body)}


def inbox(*, limit: int = 20, with_n: str | None = None, cfg: Config | None = None) -> dict[str, Any]:
    cfg = cfg or load()
    peer = normalize(with_n) if with_n else None
    messages = []
    source = "provider"
    try:
        messages = get_provider(cfg).list_messages(limit=limit, with_n=peer)
        con = connect(cfg.db_path)
        for m in messages:
            upsert_message(con, m, source="provider")
        con.close()
    except (ProviderError, NotImplementedError):
        source = "local"
        con = connect(cfg.db_path)
        messages = list_local(con, limit=limit, with_n=peer)
        con.close()
    return {
        "ok": True,
        "source": source,
        "messages": [m.to_dict() for m in messages],
    }


def thread(with_n: str, *, limit: int = 40, cfg: Config | None = None) -> dict[str, Any]:
    return inbox(limit=limit, with_n=with_n, cfg=cfg)


def call(
    to: str,
    *,
    say: str | None = None,
    url: str | None = None,
    yes: bool = False,
    force: bool = False,
    cfg: Config | None = None,
) -> dict[str, Any]:
    cfg = cfg or load()
    dest = normalize(to)
    require_yes(yes=yes, auto=cfg.auto_confirm, what=f"Place voice call to {dest}?", note=call_cost_note())
    _rate(cfg, "call", cfg.daily_call_limit, force)
    result = get_provider(cfg).place_call(dest, say=say, twiml_url=url)
    return {"ok": True, "call": result.to_dict(), "cost": call_cost_note()}


def set_webhook(url: str, *, number: str | None = None, cfg: Config | None = None) -> dict[str, Any]:
    cfg = cfg or load()
    if not url.startswith("https://") and not url.startswith("http://"):
        raise ProviderError("webhook URL must be http(s)")
    data = get_provider(cfg).set_sms_webhook(url, number)
    return {"ok": True, **data}


def _rate(cfg: Config, kind: str, limit: int, force: bool) -> None:
    con = connect(cfg.db_path)
    used = usage_today(con, kind)
    if used >= limit and not force:
        con.close()
        raise ProviderError(
            f"daily {kind} limit reached ({used}/{limit}). Pass --force to override, or raise daily_{kind}_limit in config."
        )
    bump_usage(con, kind)
    con.close()


def _usage(cfg: Config) -> dict[str, int]:
    con = connect(cfg.db_path)
    data = {"sms": usage_today(con, "sms"), "call": usage_today(con, "call")}
    con.close()
    return data
