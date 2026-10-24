"""HTTP-сервер для Telegram Mini App: статика и JSON API."""

import hashlib
import hmac
import html
import logging
import time

from aiogram import Bot
from aiogram.utils.web_app import WebAppUser, safe_parse_webapp_init_data
from aiohttp import web

from .config import BASE_DIR, Config
from .db import Database
from .texts import DEFAULT_LANG, LANGS, t

log = logging.getLogger(__name__)

WEBAPP_DIR = BASE_DIR / "webapp"
BRAND_DIR = BASE_DIR / "assets"
INIT_DATA_TTL = 24 * 60 * 60  # initData старше суток не принимаем

CONFIG = web.AppKey("config", Config)
DB = web.AppKey("db", Database)
BOT = web.AppKey("bot", Bot)


# --- авторизация через Telegram initData ---


def current_user(request: web.Request) -> WebAppUser | None:
    """Проверяет подпись initData от Telegram. Подделать её без токена бота нельзя."""
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data:
        return None
    try:
        data = safe_parse_webapp_init_data(request.app[CONFIG].bot_token, init_data)
    except ValueError:
        return None
    if time.time() - data.auth_date.timestamp() > INIT_DATA_TTL:
        return None
    return data.user


def require_user(request: web.Request) -> WebAppUser:
    user = current_user(request)
    if user is None:
        raise web.HTTPUnauthorized(text='{"error": "unauthorized"}', content_type="application/json")
    return user


def require_admin(request: web.Request) -> WebAppUser:
    user = require_user(request)
    if not request.app[CONFIG].is_admin(user.id):
        raise web.HTTPForbidden(text='{"error": "forbidden"}', content_type="application/json")
    return user


# --- фото: доступ по подписанной ссылке (в <img> нельзя передать заголовок) ---


def photo_token(config: Config, complaint_id: int) -> str:
    return hmac.new(config.bot_token.encode(), f"photo:{complaint_id}".encode(), hashlib.sha256).hexdigest()[:24]


def photo_url(config: Config, complaint_id: int) -> str:
    return f"/api/photo/{complaint_id}?t={photo_token(config, complaint_id)}"


def display_name(row: dict) -> str:
    if row.get("first_name"):
        return row["first_name"]
    if row.get("username"):
        return "@" + row["username"]
    return f"#{str(row['user_id'])[-4:]}"


# --- страницы ---


async def index(request: web.Request) -> web.FileResponse:
    return web.FileResponse(WEBAPP_DIR / "index.html", headers={"Cache-Control": "no-cache"})


async def health(request: web.Request) -> web.Response:
    """Проверка живости для хостинга."""
    return web.json_response({"status": "ok"})


# --- API ---


async def api_map(request: web.Request) -> web.Response:
    db = request.app[DB]
    return web.json_response({"points": await db.map_points(), "stats": await db.stats()})


async def api_me(request: web.Request) -> web.Response:
    user = require_user(request)
    config, db = request.app[CONFIG], request.app[DB]
    lang = await db.get_lang(user.id) or ("ky" if (user.language_code or "").startswith("ky") else DEFAULT_LANG)
    complaints = await db.user_complaints(user.id)
    for item in complaints:
        item["photo_url"] = photo_url(config, item["id"])
    approved = sum(1 for c in complaints if c["status"] == "approved")
    return web.json_response(
        {
            "user": {
                "id": user.id,
                "first_name": user.first_name,
                "lang": lang,
                "approved": approved,
                "points": approved * config.reward_points,
                "is_admin": config.is_admin(user.id),
                "demo_mode": config.demo_mode,
            },
            "reward_points": config.reward_points,
            "complaints": complaints,
        }
    )


async def api_leaderboard(request: web.Request) -> web.Response:
    config, db = request.app[CONFIG], request.app[DB]
    me = current_user(request)
    rows = await db.leaderboard()
    leaders = [
        {
            "rank": i,
            "name": display_name(row),
            "approved": row["approved"],
            "points": row["approved"] * config.reward_points,
            "is_me": bool(me and me.id == row["user_id"]),
        }
        for i, row in enumerate(rows, start=1)
    ]
    return web.json_response({"leaders": leaders})


async def api_moderation(request: web.Request) -> web.Response:
    require_admin(request)
    config, db = request.app[CONFIG], request.app[DB]
    items = []
    for row in await db.moderation_queue():
        items.append(
            {
                "id": row["id"],
                "photo_url": photo_url(config, row["id"]),
                "violation_type": row["violation_type"],
                "waste_type": row["waste_type"],
                "volume_m3": row["volume_m3"],
                "burning": bool(row["burning"]),
                "confidence": row["confidence"],
                "verdict": row["verdict"],
                "ai_json": row["ai_json"],
                "lat": row["lat"],
                "lon": row["lon"],
                "address": row["address"],
                "created_at": row["created_at"],
                "reporter": display_name(row),
            }
        )
    return web.json_response({"items": items})


async def api_moderate(request: web.Request) -> web.Response:
    moderator = require_admin(request)
    config, db, bot = request.app[CONFIG], request.app[DB], request.app[BOT]
    complaint_id = int(request.match_info["complaint_id"])
    body = await request.json()
    action = body.get("action")
    if action not in {"approve", "reject"}:
        return web.json_response({"error": "bad action"}, status=400)
    comment = (body.get("comment") or "").strip()[:300] or None

    complaint = await db.get_complaint(complaint_id)
    if complaint is None:
        return web.json_response({"error": "not found"}, status=404)
    approved = action == "approve"
    if not await db.moderate(complaint_id, approved=approved, moderator_id=moderator.id, comment=comment):
        return web.json_response({"error": "already moderated"}, status=409)

    await notify_reporter(bot, db, config, complaint, approved=approved, comment=comment)
    log.info("Complaint #%s %s by %s", complaint_id, action, moderator.id)
    return web.json_response({"ok": True, "status": "approved" if approved else "rejected"})


async def notify_reporter(
    bot: Bot, db: Database, config: Config, complaint: dict, *, approved: bool, comment: str | None
) -> None:
    """Сообщает жителю о решении инспектора прямо в чат с ботом."""
    user_id = complaint["user_id"]
    lang = await db.get_lang(user_id) or DEFAULT_LANG
    if lang not in LANGS:
        lang = DEFAULT_LANG
    if approved:
        total = await db.approved_count(user_id) * config.reward_points
        text = t("moderation_approved", lang, id=complaint["id"], points=config.reward_points, total=total)
    else:
        reason = t("moderation_reason", lang, comment=html.escape(comment)) if comment else ""
        text = t("moderation_rejected", lang, id=complaint["id"], reason=reason)
    try:
        await bot.send_message(user_id, text)
    except Exception:
        log.warning("Не удалось уведомить пользователя %s", user_id, exc_info=True)


async def api_photo(request: web.Request) -> web.StreamResponse:
    config, db = request.app[CONFIG], request.app[DB]
    complaint_id = int(request.match_info["complaint_id"])
    if not hmac.compare_digest(request.query.get("t", ""), photo_token(config, complaint_id)):
        raise web.HTTPForbidden()
    complaint = await db.get_complaint(complaint_id)
    if complaint is None:
        raise web.HTTPNotFound()
    path = (config.data_dir / complaint["photo_path"]).resolve()
    if not path.is_file() or config.data_dir.resolve() not in path.parents:
        raise web.HTTPNotFound()
    return web.FileResponse(path, headers={"Cache-Control": "private, max-age=86400"})


def create_web_app(config: Config, db: Database, bot: Bot) -> web.Application:
    app = web.Application()
    app[CONFIG] = config
    app[DB] = db
    app[BOT] = bot
    app.router.add_get("/", index)
    app.router.add_get("/health", health)
    app.router.add_get("/api/map", api_map)
    app.router.add_get("/api/me", api_me)
    app.router.add_get("/api/leaderboard", api_leaderboard)
    app.router.add_get("/api/moderation", api_moderation)
    app.router.add_post("/api/moderation/{complaint_id:\\d+}", api_moderate)
    app.router.add_get("/api/photo/{complaint_id:\\d+}", api_photo)
    app.router.add_static("/static/", WEBAPP_DIR, append_version=True)
    app.router.add_static("/brand/", BRAND_DIR)
    return app
