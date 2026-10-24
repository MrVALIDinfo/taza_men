import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Config:
    bot_token: str
    gemini_api_key: str
    gemini_models: list[str]
    data_dir: Path
    daily_limit: int
    webapp_url: str | None
    web_host: str
    web_port: int
    admin_ids: frozenset[int]
    demo_mode: bool
    reward_points: int
    use_webhook: bool

    @property
    def webhook_path(self) -> str:
        return "/tg/webhook"

    @property
    def webhook_secret(self) -> str:
        # Telegram присылает его в заголовке — чужие запросы на вебхук отбрасываются
        return hashlib.sha256(f"webhook:{self.bot_token}".encode()).hexdigest()[:48]

    @property
    def photos_dir(self) -> Path:
        return self.data_dir / "photos"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "taza_men.db"

    def is_admin(self, user_id: int) -> bool:
        # В демо-режиме модерацию видят все — чтобы жюри могло пройти весь сценарий
        return self.demo_mode or user_id in self.admin_ids


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _hosting_url() -> str | None:
    """Публичный адрес, который хостинг сам кладёт в окружение (Railway, Render)."""
    if domain := os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip():
        return f"https://{domain}"
    if url := os.getenv("RENDER_EXTERNAL_URL", "").strip():
        return url.rstrip("/")
    return None


def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not bot_token:
        raise RuntimeError("BOT_TOKEN не задан в .env")
    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY не задан в .env")

    webapp_url = os.getenv("WEBAPP_URL", "").strip().rstrip("/") or _hosting_url()
    if webapp_url and not webapp_url.startswith("https://"):
        raise RuntimeError("WEBAPP_URL должен начинаться с https:// — Telegram открывает Mini App только по HTTPS")

    # polling — бот сам спрашивает Telegram (локально); webhook — Telegram сам стучится на сервер.
    # На Render вебхук обязателен: бесплатный сервис засыпает, а входящий запрос от Telegram его будит.
    bot_mode = os.getenv("BOT_MODE", "auto").strip().lower()
    if bot_mode not in {"auto", "polling", "webhook"}:
        raise RuntimeError("BOT_MODE должен быть auto, polling или webhook")
    use_webhook = bot_mode == "webhook" or (bot_mode == "auto" and bool(os.getenv("RENDER")))
    if use_webhook and not webapp_url:
        raise RuntimeError("Для BOT_MODE=webhook нужен публичный HTTPS-адрес (WEBAPP_URL)")

    config = Config(
        bot_token=bot_token,
        gemini_api_key=gemini_api_key,
        gemini_models=[
            m.strip()
            for m in os.getenv("GEMINI_MODELS", "gemini-3.5-flash,gemini-3.5-flash-lite").split(",")
            if m.strip()
        ],
        data_dir=BASE_DIR / os.getenv("DATA_DIR", "data"),
        daily_limit=int(os.getenv("DAILY_LIMIT", "10")),
        webapp_url=webapp_url,
        web_host=os.getenv("WEB_HOST", "0.0.0.0"),
        web_port=int(os.getenv("PORT", os.getenv("WEB_PORT", "8080"))),
        admin_ids=frozenset(int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x),
        demo_mode=_bool(os.getenv("DEMO_MODE", "true")),
        reward_points=int(os.getenv("REWARD_POINTS", "100")),
        use_webhook=use_webhook,
    )
    config.photos_dir.mkdir(parents=True, exist_ok=True)
    return config
