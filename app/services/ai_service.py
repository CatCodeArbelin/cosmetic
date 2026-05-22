from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from app.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    'Ты — ассистент поддержки интернет-магазина косметики. '
    'Пиши только на русском языке, обращайся к клиенту на «вы», тон дружелюбный, короткий и без давления. '
    'Нельзя обещать лечение, медицинский эффект или гарантировать результат. '
    'Если данных недостаточно, задай уточняющие вопросы перед рекомендацией. '
    'Если клиент упоминает заболевание, симптомы, диагноз или лечение, обязательно порекомендуй обратиться к врачу '
    'и давай только общие, безопасные рекомендации по уходу без медицинских назначений. '
    'Учитывай контекст базы знаний. '
    'Верни строго JSON формата: '
    '{"variants":["короткий вариант 1","короткий вариант 2"]}. '
    'Каждый вариант должен соответствовать этим правилам.'
)


def _log_ctx(dialog_id: int | str = '-', message_id: int | str = '-', external_chat_id: str = '-', operator_id: int | str = '-', action: str = '-') -> dict[str, int | str]:
    return {'dialog_id': dialog_id, 'message_id': message_id, 'external_chat_id': external_chat_id, 'operator_id': operator_id, 'action': action}


class AIService:
    def __init__(self, api_key: str, model: str, knowledge_service: KnowledgeService | None = None) -> None:
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.knowledge_service = knowledge_service or KnowledgeService()

    async def generate_variants(self, customer_text: str, dialog_id: int | None = None, message_id: int | None = None, external_chat_id: str | None = None) -> tuple[str, str]:
        context = self.knowledge_service.relevant_context(customer_text)
        user_prompt = (
            f'Сообщение клиента:\n{customer_text}\n\n'
            f'Релевантный контекст:\n{context}\n\n'
            'Сформируй 2 коротких варианта ответа клиенту.'
        )

        ctx = _log_ctx(dialog_id=dialog_id or '-', message_id=message_id or '-', external_chat_id=external_chat_id or '-', action='ai_generate')
        try:
            response = await self.client.responses.create(
                model=self.model,
                input=[
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_prompt},
                ],
                temperature=0.4,
            )
            raw_text = response.output_text
            payload = json.loads(raw_text)
            variants = payload.get('variants', [])
            if len(variants) >= 2:
                return str(variants[0]).strip(), str(variants[1]).strip()
            raise ValueError('OpenAI returned invalid variants payload')
        except Exception as exc:
            logger.exception('openai generation failed, fallback is used', extra={**ctx, 'error_type': type(exc).__name__})
            return (
                'Спасибо за сообщение! Чтобы корректно подсказать уход, уточните, пожалуйста, ваш тип кожи и что именно хотите улучшить.',
                'Благодарю за обращение! Если есть выраженные симптомы или заболевание, лучше обсудить это с врачом, а я подскажу общий и бережный уход.',
            )
