import asyncio
import html
import json
import logging
import time
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message, User

from .ai import WasteAnalyzer, fallback_report
from .config import BASE_DIR, Config
from .db import Database
from .keyboards import confirm_keyboard, lang_keyboard, location_keyboard, main_menu
from .texts import (
    DEFAULT_LANG,
    LANGS,
    STATUS_NAMES,
    VIOLATION_NAMES,
    WASTE_TYPE_NAMES,
    button_variants,
    t,
)

log = logging.getLogger(__name__)
router = Router()

LOGO_PATH = BASE_DIR / "assets" / "logo_full.png"

# Примерные границы Кыргызстана — отсекаем точки «с другого конца света»
KG_LAT = (39.1, 43.3)
KG_LON = (69.2, 80.3)

IMAGE_MIME = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}

# Telegram присылает альбом отдельными сообщениями с одним media_group_id.
# Ждём ALBUM_WAIT секунд, собираем все и берём только первое фото.
ALBUM_WAIT = 1.0
_albums: dict[str, list[Message]] = {}
_albums_done: dict[str, float] = {}


class ComplaintFlow(StatesGroup):
    waiting_location = State()  # ждём место: геолокацию или адрес текстом
    waiting_confirm = State()   # показали карточку, ждём «Подтвердить»


async def get_lang(db: Database, user: User) -> str:
    lang = await db.get_lang(user.id)
    if lang:
        return lang
    return "ky" if (user.language_code or "").startswith("ky") else DEFAULT_LANG


async def cancel_draft(state: FSMContext, db: Database) -> None:
    """Если пользователь бросил незавершённую жалобу — помечаем её отменённой."""
    if await state.get_state() in (ComplaintFlow.waiting_location.state, ComplaintFlow.waiting_confirm.state):
        data = await state.get_data()
        if complaint_id := data.get("complaint_id"):
            await db.set_status(complaint_id, "cancelled")
    await state.clear()


async def first_of_album(message: Message) -> tuple[Message | None, bool]:
    """Возвращает (первое сообщение альбома, был_ли_альбом). None — сообщение пропускаем."""
    group_id = message.media_group_id
    if group_id is None:
        return message, False

    now = time.monotonic()
    for gid, done_at in list(_albums_done.items()):
        if now - done_at > 60:
            del _albums_done[gid]

    if group_id in _albums_done:
        return None, True
    if group_id in _albums:
        _albums[group_id].append(message)
        return None, True

    _albums[group_id] = [message]
    await asyncio.sleep(ALBUM_WAIT)
    messages = _albums.pop(group_id)
    _albums_done[group_id] = time.monotonic()
    return min(messages, key=lambda m: m.message_id), True


def in_kyrgyzstan(lat: float, lon: float) -> bool:
    return KG_LAT[0] <= lat <= KG_LAT[1] and KG_LON[0] <= lon <= KG_LON[1]


def format_volume(volume: float) -> str:
    if volume < 1:
        return f"{volume:.1f}".rstrip("0").rstrip(".") or "<1"
    return f"{volume:.0f}"


_logo_file_id: str | None = None  # после первой загрузки логотип отправляется по file_id — мгновенно


async def remove_message(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


async def send_welcome(message: Message, lang: str) -> None:
    global _logo_file_id
    if not LOGO_PATH.exists():
        await message.answer(t("welcome", lang), reply_markup=main_menu(lang))
        return
    await message.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)
    sent = await message.answer_photo(
        _logo_file_id or FSInputFile(LOGO_PATH), caption=t("welcome", lang), reply_markup=main_menu(lang)
    )
    _logo_file_id = sent.photo[-1].file_id


# --- старт и язык ---


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: Database) -> None:
    lang = await db.get_lang(message.from_user.id)
    loading = await message.answer(t("loading", lang) if lang else t("loading_any", DEFAULT_LANG))
    try:
        await cancel_draft(state, db)
        if lang is None:
            await message.answer(t("choose_lang", DEFAULT_LANG), reply_markup=lang_keyboard())
        else:
            await send_welcome(message, lang)
    finally:
        await remove_message(loading)


@router.message(Command("lang"))
@router.message(F.text.in_(button_variants("btn_lang")))
async def cmd_lang(message: Message, state: FSMContext, db: Database) -> None:
    await cancel_draft(state, db)
    await message.answer(t("choose_lang", DEFAULT_LANG), reply_markup=lang_keyboard())


@router.callback_query(F.data.startswith("lang:"))
async def on_lang_chosen(callback: CallbackQuery, db: Database) -> None:
    lang = callback.data.split(":", 1)[1]
    if lang not in LANGS:
        await callback.answer()
        return
    await db.set_lang(callback.from_user.id, lang, callback.from_user.username, callback.from_user.first_name)
    await callback.answer()
    await callback.message.edit_text(t("loading", lang))
    await send_welcome(callback.message, lang)
    await callback.message.edit_text(t("lang_set", lang))


# --- меню ---


@router.message(Command("report"))
@router.message(F.text.in_(button_variants("btn_report")))
async def cmd_report(message: Message, state: FSMContext, db: Database) -> None:
    await cancel_draft(state, db)
    lang = await get_lang(db, message.from_user)
    await message.answer(t("ask_photo", lang), reply_markup=main_menu(lang))


@router.message(Command("my"))
@router.message(F.text.in_(button_variants("btn_my")))
async def cmd_my(message: Message, state: FSMContext, db: Database) -> None:
    await cancel_draft(state, db)
    lang = await get_lang(db, message.from_user)
    rows = await db.list_user_complaints(message.from_user.id)
    if not rows:
        await message.answer(t("my_empty", lang), reply_markup=main_menu(lang))
        return

    lines = [t("my_header", lang), ""]
    for row in rows:
        date = datetime.fromisoformat(row["created_at"]).strftime("%d.%m.%Y")
        violation = VIOLATION_NAMES.get(row["violation_type"] or "none", VIOLATION_NAMES["none"])[lang]
        status = STATUS_NAMES.get(row["status"], {}).get(lang, row["status"])
        lines.append(t("my_row", lang, id=row["id"], date=date, violation=violation, status=status))
    await message.answer("\n".join(lines), reply_markup=main_menu(lang))


@router.message(Command("help"))
@router.message(F.text.in_(button_variants("btn_about")))
async def cmd_about(message: Message, state: FSMContext, db: Database) -> None:
    await cancel_draft(state, db)
    lang = await get_lang(db, message.from_user)
    await message.answer(t("about", lang), reply_markup=main_menu(lang))


# --- фото → AI ---


@router.message(F.photo)
async def on_photo(
    message: Message, state: FSMContext, bot: Bot, db: Database, analyzer: WasteAnalyzer, config: Config
) -> None:
    first, was_album = await first_of_album(message)
    if first is None:
        return
    photo = first.photo[-1]  # самое большое разрешение
    await process_image(
        first, state, bot, db, analyzer, config,
        file_id=photo.file_id, unique_id=photo.file_unique_id,
        mime_type="image/jpeg", was_album=was_album, as_photo=True,
    )


@router.message(F.document.mime_type.in_(IMAGE_MIME.keys()))
async def on_image_document(
    message: Message, state: FSMContext, bot: Bot, db: Database, analyzer: WasteAnalyzer, config: Config
) -> None:
    first, was_album = await first_of_album(message)
    if first is None:
        return
    doc = first.document
    await process_image(
        first, state, bot, db, analyzer, config,
        file_id=doc.file_id, unique_id=doc.file_unique_id,
        mime_type=doc.mime_type, was_album=was_album, as_photo=False,
    )


async def process_image(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db: Database,
    analyzer: WasteAnalyzer,
    config: Config,
    *,
    file_id: str,
    unique_id: str,
    mime_type: str,
    was_album: bool,
    as_photo: bool,
) -> None:
    user_id = message.from_user.id
    lang = await get_lang(db, message.from_user)
    await cancel_draft(state, db)
    await db.update_names(user_id, message.from_user.username, message.from_user.first_name)

    if await db.count_today(user_id) >= config.daily_limit:
        await message.answer(t("limit", lang, limit=config.daily_limit), reply_markup=main_menu(lang))
        return

    if was_album:
        await message.answer(t("album_first_only", lang))
    progress = await message.answer(t("analyzing", lang))
    await bot.send_chat_action(message.chat.id, ChatAction.TYPING)

    photo_path = config.photos_dir / f"{user_id}_{message.message_id}_{unique_id}.{IMAGE_MIME[mime_type]}"
    await bot.download(file_id, destination=photo_path)

    ai_ok = True
    try:
        report = await analyzer.analyze(photo_path.read_bytes(), mime_type)
    except Exception:
        log.exception("Gemini analysis failed for user %s", user_id)
        report = fallback_report()
        ai_ok = False

    complaint_id = await db.create_complaint(
        user_id=user_id,
        photo_path=photo_path.relative_to(config.data_dir).as_posix(),
        file_id=file_id,
        ai_json=report.model_dump_json(),
        verdict=report.verdict,
        violation_type=report.violation_type,
        waste_type=report.waste_type,
        volume_m3=report.volume_m3,
        burning=report.burning,
        confidence=report.confidence,
        status="rejected_ai" if report.verdict == "reject" else "draft",
    )
    log.info("Complaint #%s from %s: %s", complaint_id, user_id, report.model_dump_json())

    try:
        await progress.delete()
    except Exception:
        pass

    reason = html.escape(report.reason_ky if lang == "ky" else report.reason_ru)

    if report.verdict == "reject":
        await message.answer(t("rejected", lang, reason=reason), reply_markup=main_menu(lang))
        return

    if ai_ok:
        parts = [
            t(
                "accepted", lang,
                violation=VIOLATION_NAMES[report.violation_type][lang],
                waste_type=WASTE_TYPE_NAMES[report.waste_type][lang],
                volume=format_volume(report.volume_m3),
                burning=t("burning", lang) if report.burning else "",
                confidence=round(report.confidence * 100),
                reason=reason,
            )
        ]
        if report.verdict == "needs_review":
            parts.append(t("review_note", lang))
    else:
        parts = [t("ai_unavailable", lang)]
    parts.append(t("send_location", lang))

    await state.set_state(ComplaintFlow.waiting_location)
    await state.update_data(
        complaint_id=complaint_id,
        violation_type=report.violation_type,
        photo_path=photo_path.as_posix(),
        # file_id из альбома-фото можно переслать мгновенно; картинку-документ отправим файлом
        photo_file_id=file_id if as_photo else None,
    )
    await message.answer("\n\n".join(parts), reply_markup=location_keyboard(lang))


# --- место нарушения: геолокация или адрес текстом ---


PLACE_STATES = (ComplaintFlow.waiting_location, ComplaintFlow.waiting_confirm)
ADDRESS_MIN, ADDRESS_MAX = 5, 300


def place_text(lang: str, data: dict) -> str:
    if data.get("address"):
        return f"<i>{html.escape(data['address'])}</i>"
    lat, lon = data["lat"], data["lon"]
    return t("place_geo", lang, lat=f"{lat:.5f}", lon=f"{lon:.5f}")


async def show_summary(message: Message, state: FSMContext, bot: Bot, lang: str) -> None:
    """Карточка обращения с кнопками «Подтвердить» / «Отменить»."""
    data = await state.get_data()

    # у прошлой карточки (если место меняли) убираем кнопки, чтобы не подтвердить старую версию
    if old_id := data.get("summary_message_id"):
        try:
            await bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=old_id, reply_markup=None)
        except Exception:
            pass

    violation_type = data.get("violation_type", "none")
    violation = (
        VIOLATION_NAMES[violation_type][lang] if violation_type != "none" else t("violation_unknown", lang)
    )
    caption = t("summary", lang, id=data["complaint_id"], violation=violation, place=place_text(lang, data))
    keyboard = confirm_keyboard(lang, data["complaint_id"])
    photo = data.get("photo_file_id") or FSInputFile(data["photo_path"])
    summary = await message.answer_photo(photo, caption=caption, reply_markup=keyboard)

    await state.set_state(ComplaintFlow.waiting_confirm)
    await state.update_data(summary_message_id=summary.message_id)


@router.message(StateFilter(*PLACE_STATES), F.text.in_(button_variants("btn_cancel")))
async def on_cancel(message: Message, state: FSMContext, bot: Bot, db: Database) -> None:
    lang = await get_lang(db, message.from_user)
    data = await state.get_data()
    if summary_id := data.get("summary_message_id"):
        try:
            await bot.edit_message_reply_markup(chat_id=message.chat.id, message_id=summary_id, reply_markup=None)
        except Exception:
            pass
    await cancel_draft(state, db)
    await message.answer(t("cancelled", lang), reply_markup=main_menu(lang))


@router.message(StateFilter(*PLACE_STATES), F.location)
async def on_place_location(message: Message, state: FSMContext, bot: Bot, db: Database) -> None:
    lang = await get_lang(db, message.from_user)
    location = message.location
    if not in_kyrgyzstan(location.latitude, location.longitude):
        await message.answer(t("outside_kg", lang), reply_markup=location_keyboard(lang))
        return
    await state.update_data(lat=location.latitude, lon=location.longitude, address=None)
    await show_summary(message, state, bot, lang)


@router.message(StateFilter(*PLACE_STATES), F.web_app_data)
async def on_place_from_map(message: Message, state: FSMContext, bot: Bot, db: Database) -> None:
    """Точка, выбранная в Mini App («Указать на карте»), приходит как web_app_data."""
    lang = await get_lang(db, message.from_user)
    try:
        point = json.loads(message.web_app_data.data)
        lat, lon = float(point["lat"]), float(point["lon"])
    except (ValueError, KeyError, TypeError):
        await message.answer(t("bad_pick", lang), reply_markup=location_keyboard(lang))
        return
    if not in_kyrgyzstan(lat, lon):
        await message.answer(t("outside_kg", lang), reply_markup=location_keyboard(lang))
        return
    await state.update_data(lat=lat, lon=lon, address=None)
    await show_summary(message, state, bot, lang)


@router.message(StateFilter(*PLACE_STATES), F.text, ~F.text.startswith("/"))
async def on_place_address(message: Message, state: FSMContext, bot: Bot, db: Database) -> None:
    lang = await get_lang(db, message.from_user)
    address = " ".join(message.text.split())
    if len(address) < ADDRESS_MIN:
        await message.answer(t("address_too_short", lang), reply_markup=location_keyboard(lang))
        return
    await state.update_data(address=address[:ADDRESS_MAX], lat=None, lon=None)
    await show_summary(message, state, bot, lang)


@router.message(StateFilter(*PLACE_STATES))
async def on_place_other(message: Message, db: Database) -> None:
    lang = await get_lang(db, message.from_user)
    await message.answer(t("need_place", lang), reply_markup=location_keyboard(lang))


# --- подтверждение ---


async def close_summary(callback: CallbackQuery, suffix: str) -> None:
    """Убирает кнопки с карточки и дописывает итог («Подтверждено» / «Отменено»)."""
    try:
        await callback.message.edit_caption(caption=callback.message.html_text + suffix, reply_markup=None)
    except Exception:
        await callback.message.edit_reply_markup(reply_markup=None)


async def active_complaint(callback: CallbackQuery, state: FSMContext) -> int | None:
    """id жалобы из кнопки, если она совпадает с текущей карточкой пользователя."""
    complaint_id = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    if await state.get_state() != ComplaintFlow.waiting_confirm.state or data.get("complaint_id") != complaint_id:
        return None
    return complaint_id


@router.callback_query(F.data.startswith("confirm:"))
async def on_confirm(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_lang(db, callback.from_user)
    complaint_id = await active_complaint(callback, state)
    if complaint_id is None:
        await callback.answer(t("already_done", lang), show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    data = await state.get_data()
    await db.submit_complaint(complaint_id, lat=data.get("lat"), lon=data.get("lon"), address=data.get("address"))
    await state.clear()
    await close_summary(callback, t("summary_confirmed", lang))
    await callback.message.answer(t("sent", lang, id=complaint_id), reply_markup=main_menu(lang))
    await callback.answer()


@router.callback_query(F.data.startswith("discard:"))
async def on_discard(callback: CallbackQuery, state: FSMContext, db: Database) -> None:
    lang = await get_lang(db, callback.from_user)
    complaint_id = await active_complaint(callback, state)
    if complaint_id is None:
        await callback.answer(t("already_done", lang), show_alert=True)
        await callback.message.edit_reply_markup(reply_markup=None)
        return

    await cancel_draft(state, db)
    await close_summary(callback, t("summary_cancelled", lang))
    await callback.message.answer(t("cancelled", lang), reply_markup=main_menu(lang))
    await callback.answer()


@router.message(F.location)
async def on_location_without_photo(message: Message, db: Database) -> None:
    lang = await get_lang(db, message.from_user)
    await message.answer(t("photo_first", lang), reply_markup=main_menu(lang))


# --- всё остальное ---


@router.message(F.video | F.video_note | F.animation | F.document | F.sticker | F.voice)
async def on_not_photo(message: Message, db: Database) -> None:
    if message.media_group_id:
        return  # видео из смешанного альбома — молча пропускаем, фото обработается отдельно
    lang = await get_lang(db, message.from_user)
    await message.answer(t("only_photo", lang), reply_markup=main_menu(lang))


@router.message()
async def on_anything_else(message: Message, db: Database) -> None:
    lang = await get_lang(db, message.from_user)
    await message.answer(t("fallback", lang), reply_markup=main_menu(lang))
