from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from .texts import t

# Адрес Mini App задаётся при запуске; без него кнопки карты просто не показываются
_webapp_url: str | None = None


def set_webapp_url(url: str | None) -> None:
    global _webapp_url
    _webapp_url = url


def webapp_info(lang: str, **params: str) -> WebAppInfo:
    query = "&".join(f"{key}={value}" for key, value in {**params, "lang": lang}.items())
    return WebAppInfo(url=f"{_webapp_url}/?{query}")


def lang_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇰🇬 Кыргызча", callback_data="lang:ky"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
            ]
        ]
    )


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=t("btn_report", lang))]]
    if _webapp_url:
        rows.append([KeyboardButton(text=t("btn_map", lang), web_app=webapp_info(lang))])
    rows += [
        [KeyboardButton(text=t("btn_my", lang)), KeyboardButton(text=t("btn_about", lang))],
        [KeyboardButton(text=t("btn_lang", lang))],
    ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def confirm_keyboard(lang: str, complaint_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_confirm", lang), callback_data=f"confirm:{complaint_id}")],
            [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data=f"discard:{complaint_id}")],
        ]
    )


def location_keyboard(lang: str) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton(text=t("btn_location", lang), request_location=True)]]
    if _webapp_url:
        # Mini App, открытая с reply-кнопки, может вернуть выбранную точку через sendData
        rows.append([KeyboardButton(text=t("btn_pick_map", lang), web_app=webapp_info(lang, mode="pick"))])
    rows.append([KeyboardButton(text=t("btn_cancel", lang))])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder=t("address_placeholder", lang),
    )
