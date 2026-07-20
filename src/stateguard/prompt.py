from __future__ import annotations

from pathlib import Path

from .db import Ledger
from .findings import list_open_findings
from .util import atomic_write, utc_now


def generate_fix_prompt(ledger: Ledger, output: Path) -> int:
    findings = list_open_findings(ledger)
    lines = [
        "# StateGuard: задание на исправление",
        "",
        f"Сформировано: {utc_now()}",
        "",
        "## Роль",
        "",
        "Ты — инженер, исправляющий доказанные или воспроизводимые дефекты бизнес-приложения.",
        "Работай системно: устраняй корневую причину и сохраняй доменные инварианты, а не маскируй симптом.",
        "",
        "## Обязательный цикл",
        "",
        "1. Прочитай `.stateguard/specification.yaml`, `.stateguard/mappings.yaml` и этот каталог находок.",
        "2. Для каждой находки сначала воспроизведи counterexample или добавь тест, который его фиксирует.",
        "3. Исправь минимальный цельный вертикальный срез: вход, guard, транзакцию, БД, ответ и UI-проекцию.",
        "4. Не ослабляй ограничения базы и не заменяй ожидаемый отказ молчаливым значением по умолчанию.",
        "5. После изменений выполни `stateguard scan`, соответствующие анализаторы и тесты.",
        "6. Переведи finding в `fixed-pending-verification`; закрывать его можно только независимой проверкой.",
        "7. Финальная проверка: `stateguard doctor --strict`.",
        "",
        "## Правила безопасного исправления",
        "",
        "- Не меняй требования неявно. Неоднозначность оформляй как specification gap.",
        "- Для конкурентных изменений используй условный atomic update, lock, constraint или SERIALIZABLE с полным retry.",
        "- Не выполняй необратимые внешние эффекты внутри повторяемой транзакции; применяй outbox/idempotency.",
        "- Сервер и база являются источником истины; клиент не должен подтверждать неподтверждённое состояние.",
        "- Любой новый путь отказа должен иметь типизированный результат и наблюдаемость.",
        "",
        "## Находки",
        "",
    ]

    if not findings:
        lines.append("Открытых находок нет.")
    for finding in findings:
        location = finding["file_path"] or "<без файла>"
        if finding["start_line"]:
            location += f":{finding['start_line']}"
        lines.extend(
            [
                f"### SG-{finding['id']:05d} · {finding['severity'].upper()} · {finding['title']}",
                "",
                f"- Статус: `{finding['status']}`",
                f"- Источник: `{finding['source_tool']}` / `{finding['rule_id']}`",
                f"- Место: `{location}`",
                f"- Категория: `{finding['category']}`",
                f"- Инвариант: `{finding['invariant_id'] or 'не связан'}`",
                f"- Переход: `{finding['transition_id'] or 'не связан'}`",
                "",
                "**Наблюдение**",
                "",
                finding["message"],
                "",
                "**Counterexample**",
                "",
                finding["counterexample"] or "Требуется сформулировать и зафиксировать воспроизводимый сценарий.",
                "",
                "**Воздействие**",
                "",
                finding["impact"] or "Требуется определить до изменения кода.",
                "",
                "**Корневая причина**",
                "",
                finding["root_cause"] or "Требуется подтвердить анализом вертикального среза.",
                "",
                "**Требуемое исправление**",
                "",
                finding["remediation"] or "Устранить путь в запрещённое состояние и закрепить инвариант.",
                "",
                "**Критерий проверки**",
                "",
                finding["verification"] or "Добавить негативный тест и повторить анализ изменённого среза.",
                "",
            ]
        )

    atomic_write(output, "\n".join(lines).rstrip() + "\n")
    return len(findings)
