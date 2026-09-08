#!/usr/bin/env python3
"""
Technical SEO Score — /root/seo/tools/score-audit.py

Рассчитывает взвешенную оценку 0-100 из JSON-отчёта crawl-site.py.

Шкала:
  90-100  Отлично
  70-89   Хорошо
  50-69   Удовлетворительно
  30-49   Плохо
  0-29    Критично

Запуск:
  python3 score-audit.py <report.json>
  python3 score-audit.py <report.json> --verbose
"""

import argparse
import json
import sys

# ─── Веса проверок ───────────────────────────────────────────────────────────

# Максимум 100 баллов
WEIGHTS = {
    # Критические (стоп) — каждый -15
    'title-отсутствует':     -15,
    'description-отсутствует': -15,
    'h1-отсутствует':        -15,
    'robots-noindex':        -15,

    # Серьёзные (чинить) — каждый -5
    'canonical-отсутствует':  -5,
    'http-вместо-https':      -5,
    'robots-nofollow':        -3,
    'h1-несколько':           -5,
    'title-короткий':         -3,
    'title-длинный':          -3,
    'description-короткая':   -3,
    'description-длинная':     -3,
    'img-без-alt':            -5,  # за каждые 5 изображений -1
    'img-без-размеров':       -3,
    'viewport-отсутствует':    -5,
    'страница-большая':        -5,
    'страница-тяжёлая':        -3,

    # Заметки — каждый -1
    'h2-отсутствует':         -1,
    'og-неполный':             -2,
    'canonical-отличается':     -1,
    'h1-длинный':              -1,
    'json-ld-отсутствует':     -2,
}

DEFAULT_PENALTY = -3  # Неизвестная проверка

def score_finding(finding: dict) -> int:
    """Рассчитывает штраф за одну проверку."""
    check = finding['check']
    level = finding['level']

    if level == 'stop':
        # Стоп — фиксированный штраф
        return WEIGHTS.get(check, -15)

    if level == 'fix':
        # Чинить — есть нюансы
        if check == 'img-без-alt':
            # Парсим количество из сообщения
            msg = finding['message']
            match = json.dumps(msg)  # упрощённо
            return -5  # базовый штраф за наличие
        return WEIGHTS.get(check, DEFAULT_PENALTY)

    if level == 'note':
        return WEIGHTS.get(check, -1)

    return 0

def score_report(report: dict) -> dict:
    """Рассчитывает общую оценку из отчёта."""
    findings = report.get('findings', [])

    # Базовый балл
    score = 100
    penalties = []

    for finding in findings:
        penalty = score_finding(finding)
        if penalty != 0:
            penalties.append({
                'check': finding['check'],
                'level': finding['level'],
                'penalty': penalty,
                'message': finding['message'],
            })
            score += penalty  # штрафы отрицательные

    # Ограничиваем диапазон
    score = max(0, min(100, score))

    # Уровень
    if score >= 90:
        grade = 'Отлично'
        emoji = '🏆'
    elif score >= 70:
        grade = 'Хорошо'
        emoji = '✅'
    elif score >= 50:
        grade = 'Удовлетворительно'
        emoji = '⚠️'
    elif score >= 30:
        grade = 'Плохо'
        emoji = '🔴'
    else:
        grade = 'Критично'
        emoji = '🚨'

    # Подсчёты
    counts = {
        'stop': len([p for p in penalties if p['level'] == 'stop']),
        'fix': len([p for p in penalties if p['level'] == 'fix']),
        'note': len([p for p in penalties if p['level'] == 'note']),
    }

    return {
        'score': score,
        'grade': grade,
        'emoji': emoji,
        'counts': counts,
        'penalties': sorted(penalties, key=lambda p: p['penalty']),
        'target': report.get('target', ''),
        'timestamp': report.get('timestamp', ''),
    }

# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Technical SEO Score Calculator')
    parser.add_argument('report', help='Путь к JSON-отчёту от crawl-site.py')
    parser.add_argument('--verbose', '-v', action='store_true', help='Показать все штрафы')
    parser.add_argument('--output', '-o', help='Сохранить результат в JSON')
    args = parser.parse_args()

    with open(args.report, encoding='utf-8') as f:
        report = json.load(f)

    result = score_report(report)

    # Вывод
    print(f"\n{'='*60}")
    print(f"{result['emoji']} ОЦЕНКА ТЕХНИЧЕСКОГО SEO")
    print(f"{'='*60}")
    print(f"URL:    {result['target']}")
    print(f"Дата:   {result['timestamp']}")
    print(f"\n📊 Общий балл: {result['score']}/100 — {result['grade']}")
    print(f"\nНарушения:")
    print(f"  🔴 Стоп:  {result['counts']['stop']}")
    print(f"  🟡 Чинить: {result['counts']['fix']}")
    print(f"  🔵 Заметки: {result['counts']['note']}")

    if args.verbose and result['penalties']:
        print(f"\n{'─'*60}")
        print("Штрафы:")
        for p in result['penalties']:
            print(f"  {p['penalty']:+d}  [{p['level']}] {p['check']}")
            print(f"       {p['message'][:70]}")

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Результат сохранён: {args.output}")

if __name__ == '__main__':
    main()
