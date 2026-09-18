"""Load ~/.grok/cell config + secrets. Env wins. Never print secrets."""

from __future__ import annotations

import os
import stat
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SMS_LIMIT = 20
DEFAULT_CALL_LIMIT = 5
DEFAULT_PORT = 8788


def grok_home() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home()) / ".grok"


def data_dir() -> Path:
    override = os.environ.get("CELL_HOME")
    if override:
        return Path(override)
    return grok_home() / "cell"


@dataclass
class Config:
    provider: str = "twilio"
    from_number: str = ""
    daily_sms_limit: int = DEFAULT_SMS_LIMIT
    daily_call_limit: int = DEFAULT_CALL_LIMIT
    auto_confirm: bool = False
    webhook_port: int = DEFAULT_PORT
    public_url: str = ""
    country: str = "US"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    telnyx_api_key: str = ""
    home: Path = field(default_factory=data_dir)

    @property
    def config_path(self) -> Path:
        return self.home / "config.toml"

    @property
    def secrets_path(self) -> Path:
        return self.home / "secrets.toml"

    @property
    def db_path(self) -> Path:
        return self.home / "state.sqlite"

    def masked(self) -> dict:
        return {
            "provider": self.provider,
            "from_number": self.from_number or None,
            "daily_sms_limit": self.daily_sms_limit,
            "daily_call_limit": self.daily_call_limit,
            "auto_confirm": self.auto_confirm,
            "webhook_port": self.webhook_port,
            "public_url": self.public_url or None,
            "country": self.country,
            "home": str(self.home),
            "twilio_account_sid": _mask(self.twilio_account_sid),
            "twilio_auth_token": _present(self.twilio_auth_token),
            "telnyx_api_key": _present(self.telnyx_api_key),
        }


def load() -> Config:
    home = data_dir()
    home.mkdir(parents=True, exist_ok=True)
    cfg = Config(home=home)
    _apply_toml(cfg, _read_toml(home / "config.toml"))
    secrets = _read_toml(home / "secrets.toml")
    _apply_secrets(cfg, secrets)
    env_file = os.environ.get("CELL_ENV_FILE")
    if env_file:
        _apply_env_map(cfg, _read_env_file(Path(env_file)))
    _apply_environ(cfg)
    if cfg.provider:
        cfg.provider = cfg.provider.strip().lower()
    return cfg


def write_init(
    *,
    provider: str = "twilio",
    from_number: str = "",
    twilio_account_sid: str = "",
    twilio_auth_token: str = "",
    telnyx_api_key: str = "",
    import_env: Path | None = None,
) -> Config:
    home = data_dir()
    home.mkdir(parents=True, exist_ok=True)
    imported: dict[str, str] = {}
    if import_env:
        imported = _read_env_file(import_env)
    sid = twilio_account_sid or imported.get("TWILIO_ACCOUNT_SID") or os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = twilio_auth_token or imported.get("TWILIO_AUTH_TOKEN") or os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_n = (
        from_number
        or imported.get("CELL_FROM")
        or imported.get("TWILIO_PHONE_NUMBER")
        or os.environ.get("CELL_FROM")
        or os.environ.get("TWILIO_PHONE_NUMBER")
        or ""
    )
    tkey = telnyx_api_key or imported.get("TELNYX_API_KEY") or os.environ.get("TELNYX_API_KEY", "")
    prov = (provider or imported.get("CELL_PROVIDER") or os.environ.get("CELL_PROVIDER") or "twilio").lower()
    config_path = home / "config.toml"
    if not config_path.exists():
        config_path.write_text(
            (
                f'provider = "{_toml_str(prov)}"\n'
                f'from_number = "{_toml_str(from_n)}"\n'
                f"daily_sms_limit = {DEFAULT_SMS_LIMIT}\n"
                f"daily_call_limit = {DEFAULT_CALL_LIMIT}\n"
                "auto_confirm = false\n"
                f"webhook_port = {DEFAULT_PORT}\n"
                'public_url = ""\n'
                'country = "US"\n'
            ),
            encoding="utf-8",
        )
    else:
        # keep existing non-secret file; only fill from_number if empty
        pass
    secrets_path = home / "secrets.toml"
    secrets_path.write_text(
        (
            f'twilio_account_sid = "{_toml_str(sid)}"\n'
            f'twilio_auth_token = "{_toml_str(token)}"\n'
            f'telnyx_api_key = "{_toml_str(tkey)}"\n'
        ),
        encoding="utf-8",
    )
    _restrict(secrets_path)
    return load()


def _apply_toml(cfg: Config, data: dict) -> None:
    if not data:
        return
    cfg.provider = str(data.get("provider") or cfg.provider)
    cfg.from_number = str(data.get("from_number") or cfg.from_number)
    cfg.daily_sms_limit = int(data.get("daily_sms_limit") or cfg.daily_sms_limit)
    cfg.daily_call_limit = int(data.get("daily_call_limit") or cfg.daily_call_limit)
    if "auto_confirm" in data:
        cfg.auto_confirm = bool(data.get("auto_confirm"))
    cfg.webhook_port = int(data.get("webhook_port") or cfg.webhook_port)
    cfg.public_url = str(data.get("public_url") or cfg.public_url)
    cfg.country = str(data.get("country") or cfg.country)
    tw = data.get("twilio") if isinstance(data.get("twilio"), dict) else {}
    tx = data.get("telnyx") if isinstance(data.get("telnyx"), dict) else {}
    cfg.twilio_account_sid = str(tw.get("account_sid") or cfg.twilio_account_sid)
    cfg.twilio_auth_token = str(tw.get("auth_token") or cfg.twilio_auth_token)
    cfg.telnyx_api_key = str(tx.get("api_key") or cfg.telnyx_api_key)


def _apply_secrets(cfg: Config, data: dict) -> None:
    if not data:
        return
    cfg.twilio_account_sid = str(data.get("twilio_account_sid") or cfg.twilio_account_sid)
    cfg.twilio_auth_token = str(data.get("twilio_auth_token") or cfg.twilio_auth_token)
    cfg.telnyx_api_key = str(data.get("telnyx_api_key") or cfg.telnyx_api_key)
    _apply_toml(cfg, data)


def _apply_environ(cfg: Config) -> None:
    env = os.environ
    if env.get("CELL_PROVIDER"):
        cfg.provider = env["CELL_PROVIDER"]
    if env.get("CELL_FROM"):
        cfg.from_number = env["CELL_FROM"]
    if env.get("TWILIO_PHONE_NUMBER") and not cfg.from_number:
        cfg.from_number = env["TWILIO_PHONE_NUMBER"]
    if env.get("TWILIO_ACCOUNT_SID"):
        cfg.twilio_account_sid = env["TWILIO_ACCOUNT_SID"]
    if env.get("TWILIO_AUTH_TOKEN"):
        cfg.twilio_auth_token = env["TWILIO_AUTH_TOKEN"]
    if env.get("TELNYX_API_KEY"):
        cfg.telnyx_api_key = env["TELNYX_API_KEY"]
    if env.get("CELL_PUBLIC_URL"):
        cfg.public_url = env["CELL_PUBLIC_URL"]
    if env.get("CELL_AUTO_CONFIRM") in ("1", "true", "yes"):
        cfg.auto_confirm = True
    if env.get("CELL_WEBHOOK_PORT"):
        cfg.webhook_port = int(env["CELL_WEBHOOK_PORT"])


def _apply_env_map(cfg: Config, env: dict[str, str]) -> None:
    if env.get("CELL_PROVIDER"):
        cfg.provider = env["CELL_PROVIDER"]
    if env.get("CELL_FROM"):
        cfg.from_number = env["CELL_FROM"]
    if env.get("TWILIO_PHONE_NUMBER") and not cfg.from_number:
        cfg.from_number = env["TWILIO_PHONE_NUMBER"]
    if env.get("TWILIO_ACCOUNT_SID"):
        cfg.twilio_account_sid = env["TWILIO_ACCOUNT_SID"]
    if env.get("TWILIO_AUTH_TOKEN"):
        cfg.twilio_auth_token = env["TWILIO_AUTH_TOKEN"]
    if env.get("TELNYX_API_KEY"):
        cfg.telnyx_api_key = env["TELNYX_API_KEY"]
    if env.get("CELL_PUBLIC_URL"):
        cfg.public_url = env["CELL_PUBLIC_URL"]


def _read_toml(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
        return data if isinstance(data, dict) else {}
    except OSError:
        return {}


def _read_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        raise FileNotFoundError(str(path))
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.lower().startswith("export "):
            s = s[7:].strip()
        if "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k:
            out[k] = v
    return out


def _restrict(path: Path) -> None:
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _mask(value: str) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return value[:2] + "..."
    return value[:4] + "..." + value[-4:]


def _present(value: str) -> str:
    return "set" if value else "missing"


def _toml_str(value: str) -> str:
    return (value or "").replace("\\", "\\\\").replace('"', '\\"')
