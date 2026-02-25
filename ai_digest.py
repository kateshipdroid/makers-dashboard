import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY")


def generate_digest(metrics: dict, chart_data: dict) -> str:
    if not GEMINI_KEY:
        return _fallback_digest(metrics, chart_data)

    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""Ты — аналитик подписного клуба Makers Club (цена 3990₽/мес).
Клубу 1.5 месяца. Проанализируй метрики и дай краткий дайджест на русском языке.

Метрики:
- Активных подписчиков: {metrics['active']}
- MRR: {metrics['mrr']:,}₽
- Новых за неделю: {metrics['new_this_week']}
- Отток (всего): {metrics['churned']}
- Retention M1: {metrics['retention_m1']}%
- Подходят к первому продлению: {metrics['first_renewal_upcoming']}

Сегменты:
- Новые (эта неделя): {chart_data['segments'].get('new', 0)}
- Активные: {chart_data['segments'].get('active', 0)}
- Первое продление скоро: {chart_data['segments'].get('first_renewal', 0)}
- Отток: {chart_data['segments'].get('churned', 0)}

Ответь строго в формате:

📊 Состояние: [1-2 предложения о текущем состоянии]

⚡ Критичное: [что требует внимания прямо сейчас]

💡 Рекомендация: [конкретное действие]
"""

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        return _fallback_digest(metrics, chart_data)


def _fallback_digest(metrics: dict, chart_data: dict) -> str:
    first_renewal = metrics.get("first_renewal_upcoming", 0)

    lines = []
    lines.append(f"📊 **Состояние:** {metrics['active']} активных подписчиков, MRR {metrics['mrr']:,}₽. Клуб растёт — за последнюю неделю +{metrics['new_this_week']} новых.")

    if first_renewal > 0:
        lines.append(f"\n⚡ **Критичное:** {first_renewal} подписчиков подходят к первому продлению. Это первая реальная проверка retention — важно не потерять их.")
    elif metrics["churned"] > 0:
        lines.append(f"\n⚡ **Критичное:** {metrics['churned']} подписчиков уже отвалились. Retention M1: {metrics['retention_m1']}%.")
    else:
        lines.append(f"\n⚡ **Критичное:** Все подписчики пока в первом месяце — отток ещё не начался.")

    lines.append(f"\n💡 **Рекомендация:** Подготовить напоминание о ценности клуба для сегмента first_renewal. Персональное сообщение от куратора повышает retention на 15-20%.")

    return "\n".join(lines)
