from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from app.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    'Ты — ассистент поддержки интернет-магазина косметики. '
    'Пиши дружелюбно, кратко и профессионально. '
    'Учитывай контекст базы знаний. '
    'Верни строго JSON формата: '
    '{"variants":["короткий вариант 1","короткий вариант 2"]}.'
)


class AIService:
    def __init__(self, api_key: str, model: str, knowledge_service: KnowledgeService | None = None) -> None:
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.knowledge_service = knowledge_service or KnowledgeService()

    async def generate_variants(self, customer_text: str) -> tuple[str, str]:
        context = self.knowledge_service.relevant_context(customer_text)
        user_prompt = (
            f'Сообщение клиента:\n{customer_text}\n\n'
            f'Релевантный контекст:\n{context}\n\n'
            'Сформируй 2 коротких варианта ответа клиенту.'
        )

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
        except Exception:
            logger.exception('OpenAI generation failed, fallback is used')
            return (
                'Спасибо за сообщение! Подберу для вас оптимальный вариант и скоро уточню детали.',
                'Благодарим! Сейчас проверю информацию и вернусь к вам с точным ответом.',
            )
