import asyncio
import logging

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

VIOLATION_TYPES = {"illegal_dump", "waste_burning", "water_pollution", "hazardous_waste", "overflowing_bin", "none"}
WASTE_TYPES = {"household", "construction", "hazardous", "mixed", "none"}
VERDICTS = {"accept", "reject", "needs_review"}

PROMPT = """Ты — эколог-инспектор сервиса Taza Men (Кыргызстан).
Житель прислал фото. Определи, зафиксировано ли на фото нарушение экологических норм.
Если да — фото отправят в администрацию, где инспектор примет окончательное решение и назначит штраф,
а житель получит вознаграждение. Будь точным: ложная жалоба тратит время инспектора,
а пропущенное нарушение оставляет мусор в городе.

violation_type — тип нарушения:
- illegal_dump: мусор выброшен вне контейнеров — на обочине, пустыре, во дворе, в овраге
- waste_burning: горит мусор, листва, шины (виден огонь или дым)
- water_pollution: мусор или сток в реке, арыке, канале, на берегу
- hazardous_waste: шины, химия, аккумуляторы, медицинские отходы, шифер/асбест
- overflowing_bin: контейнер переполнен, мусор лежит вокруг площадки
- none: нарушения нет

НЕ нарушение: мусор аккуратно в контейнере или урне; один-два мелких предмета (обёртка, бутылка);
огороженная стройплощадка; уборка мусора; фото помещения, людей, еды, природы без мусора.

looks_fake = true, если это скриншот, фото экрана, картинка из интернета (водяные знаки, интерфейс),
рисунок или сгенерированное изображение.

verdict:
- accept: нарушение видно явно, фото реальное
- needs_review: нарушение вероятно, но фото нечёткое, тёмное, мусор виден частично или ситуация спорная
- reject: нарушения нет, фото не по теме или фейк

waste_type: household (бытовой), construction (строительный), hazardous (опасный), mixed (смешанный), none.
volume_m3: объём мусора по масштабу (мешок ≈ 0.1, багажник ≈ 0.5, кузов грузовика ≈ 5).
burning: виден огонь или дым. people_or_plates: видны лица людей или номера машин.
confidence: уверенность от 0 до 1.
reason_ky и reason_ru: одно предложение до 15 слов — что видно на фото и почему такой вердикт."""


class WasteReport(BaseModel):
    is_violation: bool
    violation_type: str = Field(
        description="illegal_dump | waste_burning | water_pollution | hazardous_waste | overflowing_bin | none"
    )
    waste_type: str = Field(description="household | construction | hazardous | mixed | none")
    volume_m3: float
    burning: bool
    people_or_plates: bool
    looks_fake: bool
    confidence: float
    verdict: str = Field(description="accept | needs_review | reject")
    reason_ky: str
    reason_ru: str

    def normalized(self) -> "WasteReport":
        """Приводит ответ модели к согласованному виду — модели не доверяем вслепую."""
        data = self.model_dump()
        if data["violation_type"] not in VIOLATION_TYPES:
            data["violation_type"] = "illegal_dump" if data["is_violation"] else "none"
        if data["waste_type"] not in WASTE_TYPES:
            data["waste_type"] = "mixed" if data["is_violation"] else "none"
        if data["verdict"] not in VERDICTS:
            data["verdict"] = "needs_review"
        data["confidence"] = min(max(data["confidence"], 0.0), 1.0)
        data["volume_m3"] = max(data["volume_m3"], 0.0)
        if data["burning"] and data["violation_type"] == "none":
            data["violation_type"] = "waste_burning"

        if data["looks_fake"] or not data["is_violation"]:
            data["verdict"] = "reject"
        elif data["verdict"] == "reject":
            # нарушение есть, но модель отклонила — пусть решает человек
            data["verdict"] = "needs_review"
        elif data["verdict"] == "accept" and data["confidence"] < 0.6:
            data["verdict"] = "needs_review"
        return WasteReport(**data)


def fallback_report() -> WasteReport:
    """Если AI недоступен — не теряем жалобу, а отдаём её на ручную проверку."""
    return WasteReport(
        is_violation=True,
        violation_type="none",
        waste_type="none",
        volume_m3=0.0,
        burning=False,
        people_or_plates=False,
        looks_fake=False,
        confidence=0.0,
        verdict="needs_review",
        reason_ky="AI убактылуу жеткиликсиз, сүрөттү оператор текшерет.",
        reason_ru="AI временно недоступен, фото проверит оператор.",
    )


class WasteAnalyzer:
    def __init__(self, api_key: str, models: list[str], timeout: float = 30.0):
        self._client = genai.Client(api_key=api_key)
        self._models = models
        self._timeout = timeout
        # Экономим токены: короткое «обдумывание» и среднее разрешение фото
        # (~1.2k токенов на запрос против ~2.1k по умолчанию, точность для свалок не страдает).
        self._config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=WasteReport,
            temperature=0.2,
            thinking_config=types.ThinkingConfig(thinking_level="low"),
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
        )

    async def analyze(self, image: bytes, mime_type: str = "image/jpeg") -> WasteReport:
        """Пробует модели по очереди: на бесплатном тарифе основная может упереться в лимит."""
        last_error: Exception | None = None
        for model in self._models:
            try:
                return await self._analyze_with(model, image, mime_type)
            except Exception as error:
                log.warning("Model %s failed: %s", model, error)
                last_error = error
        raise RuntimeError("All Gemini models failed") from last_error

    async def _analyze_with(self, model: str, image: bytes, mime_type: str) -> WasteReport:
        response = await asyncio.wait_for(
            self._client.aio.models.generate_content(
                model=model,
                contents=[types.Part.from_bytes(data=image, mime_type=mime_type), PROMPT],
                config=self._config,
            ),
            timeout=self._timeout,
        )
        usage = response.usage_metadata
        if usage:
            log.info(
                "Gemini %s tokens: prompt=%s thoughts=%s output=%s",
                model, usage.prompt_token_count, usage.thoughts_token_count, usage.candidates_token_count,
            )
        report = WasteReport.model_validate_json(response.text)
        return report.normalized()
