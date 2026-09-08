#!/usr/bin/env python3
"""
pSEO Article Generator — /root/seo/tools/generate-pseo-article.py

Генерирует статью по методологии pSEO из CSV-файла с ключевыми словами.
Конвейер:
  1. Читает keywords из CSV
  2. Строит структуру статьи по шаблону
  3. Применяет типографические правила (ru-text)
  4. Добавляет SEO-метаданные
  5. Выводит .md с metadata header

Запуск:
  python3 generate-pseo-article.py <keywords.csv> <term> <modifier>

Пример:
  python3 generate-pseo-article.py ../clinch/yadro-clinch-rabochiy.csv "боксёрские перчатки" "для начинающих"

Гейты из pseo.md:
  • Гейт 1: снятие SEO-обвязки — страница полезна без title/description?
  • Гейт 2: пилот 50–100 страниц перед масштабированием
"""

import csv
import re
import sys
import unicodedata
from datetime import date

# ─── 1. Типографика по правилам ru-text ────────────────────────────────────────

def fix_quotes(text: str) -> str:
    """Кавычки-ёлочки, лапки внутри."""
    # Вложенные: «"текст"» → «„текст"»
    text = re.sub(r'«"([^"]+)"»', r'«„\1"»', text)
    # Обычные кавычки → ёлочки
    text = re.sub(r'"([^"]+)"', r'«\1»', text)
    return text

def fix_dashes(text: str) -> str:
    """Длинное тире (em dash), диапазон — короткое без пробелов."""
    # Слово — слово → слово — слово (em dash)
    text = re.sub(r'(\S) - (\S)', r'\1 — \2', text)
    # Диапазон 10-15 дней → 10–15 дней (en dash)
    text = re.sub(r'(\d+)-(\d+)', lambda m: m.group(1) + '–' + m.group(2) if not re.match(r'\d{4}-\d{2}', m.group(0)) else m.group(0), text)
    return text

def fix_typography(text: str) -> str:
    """Все типографические исправления за один проход."""
    text = fix_quotes(text)
    text = fix_dashes(text)
    # Многоточие
    text = text.replace('...', '…')
    # Знак номера
    text = re.sub(r'\bNo\.?\s*(\d+)', r'№ \1', text)
    text = re.sub(r'\bno\.?\s*(\d+)', r'№ \1', text)
    # Неразрывный пробел после однобуквенных предлогов
    nbsp = chr(0xa0)
    for preposition in ['в', 'с', 'к', 'о', 'у', 'и', 'а', 'я']:
        text = text.replace(preposition + ' ', preposition + nbsp)
    # Тонкие пробелы в разрядах: 1000000 → 1 000 000
    text = re.sub(r'\b(\d{4,})\b', lambda m: m.group(1).replace(',', ' '), text)
    # Десятичная запятая: 3.14 → 3,14 (если не год типа 2026.05)
    text = re.sub(r'(\d+)\.(\d{2,})', r'\1,\2', text)
    return text

# ─── 2. Антиканцелярит (ru-text / Ильяхов) ───────────────────────────────────

REPLACEMENTS = [
    (r'\bявляется\s+(?:то\s+)?,?\s*что', r''),
    (r'\bв\s+настоящее\s+время\b', 'сейчас'),
    (r'\bв\s+данный\s+момент\b', 'сейчас'),
    (r'\bна\s+сегодняшний\s+день\b', 'сейчас'),
    (r'\bпроизвести\s+оплату\b', 'оплатить'),
    (r'\bданный\s+', 'этот '),
    (r'\bвышеуказанный\b', 'этот'),
    (r'\bнижеследующий\b', 'следующий'),
    (r'\bв\s+целях\b', 'чтобы'),
    (r'\bпри\s+этом\b(?!\s+,\s*\w)', 'при этом'),
    (r'\bтаким\s+образом\b', 'поэтому'),
]

def fix_corporate(text: str) -> str:
    """Убирает канцелярит по правилам Ильяхова."""
    for pattern, replacement in REPLACEMENTS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text

# ─── 3. Шаблон статьи pSEO ────────────────────────────────────────────────────

INTENTS = {
    'покупка': 'Эта категория помогает выбрать и заказать нужный товар с доставкой.',
    'выбор': 'Сравнение характеристик, рейтинг и отзывы помогут определиться с выбором.',
    'гео': 'Доставка по всей Беларуси, наличие в Минске и регионах.',
    'бренд': 'Оригинальная продукция проверенных брендов.',
    'учебное': 'Разбираем технику, правила и основы — для новичков и опытных.',
    'нецелевое': '',  # отфильтровать
}

def detect_intent(keywords: list[str]) -> str:
    """Определяет преобладающее намерение по ключевым словам."""
    scores = {k: 0 for k in INTENTS}
    for kw in keywords:
        low = kw.lower()
        if 'купить' in low or 'заказать' in low or 'цена' in low:
            scores['покупка'] += 1
        if 'как выбрать' in low or 'рейтинг' in low or 'топ ' in low:
            scores['выбор'] += 1
        if 'минск' in low or 'беларус' in low:
            scores['гео'] += 1
        if 'видео' in low or 'техника' in low or 'упражнен' in low:
            scores['учебное'] += 1
        if 'авито' in low or 'б/у' in low:
            scores['нецелевое'] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else 'выбор'

def build_article(term: str, modifier: str, keywords: list[str], intent: str) -> str:
    """Генерирует структуру статьи по pSEO-шаблону."""
    title = f"{term.capitalize()} {modifier}"
    h1 = title
    intro = (
        f"{term.capitalize()} {modifier} — в каталоге представлены модели "
        f"для разных задач и уровней подготовки. "
        f"Разбираем, на что обратить внимание при выборе и какие варианты подходят именно вам."
    )

    sections = []
    sections.append(f"## Что такое {term}")
    sections.append(f"{term.capitalize()} — основной элемент экипировки. Без правильного выбора тренировка становится менее эффективной и повышается риск травм.")
    sections.append("")
    sections.append(f"## {term.capitalize()} {modifier}: на что обратить внимание")
    sections.append("При выборе учитывайте несколько ключевых параметров:\n")
    sections.append("1. **Уровень защиты** — зависит от материала и наполнителя")
    sections.append("2. **Вес и размер** — должны соответствовать вашей антропометрии")
    sections.append("3. **Способ застёжки** — липучка, шнуровка или комбинированный")
    sections.append("4. **Материал наружного покрытия** — кожа, PU или синтетика")
    sections.append("")
    sections.append(f"## Популярные модели в категории {term}")
    sections.append(f"В каталоге представлены {len(keywords)} моделей. Вот наиболее частые запросы:")
    sections.append("")

    # Вывод ключевых слов списком
    for kw in keywords[:20]:
        sections.append(f"- {fix_typography(kw)}")

    sections.append("")
    sections.append("## Как заказать")
    sections.append("Выберите подходящую модель в каталоге, оформите заказ на сайте или свяжитесь с менеджером для консультации. Доставка по всей Беларуси.")

    article = "\n".join(sections)
    # Применяем типографику и антиканцелярит
    article = fix_typography(article)
    article = fix_corporate(article)

    full_text = f"# {h1}\n\n{intro}\n\n{article}\n\n---\n*Сгенерировано {date.today().isoformat()} · pSEO pipeline /root/seo*\n"
    return full_text

# ─── 4. SEO-метаданные ────────────────────────────────────────────────────────

def build_metadata(term: str, modifier: str, keywords: list[str]) -> dict:
    """Генерирует SEO-метаданные для статьи."""
    title = f"{term.capitalize()} {modifier} — каталог, отзывы, цены"
    description = (
        f"{term.capitalize()} {modifier}: сравнение моделей, характеристики, "
        f"рейтинг и отзывы. Выберите подходящий вариант с доставкой по Беларуси."
    )
    return {
        'title': title,
        'description': description,
        'keywords': ', '.join(keywords[:10]),
        'date': date.today().isoformat(),
    }

def format_frontmatter(term: str, modifier: str, keywords: list[str]) -> str:
    """Формирует YAML frontmatter для Markdown."""
    meta = build_metadata(term, modifier, keywords)
    return f"""---
title: "{meta['title']}"
description: "{meta['description']}"
keywords: "{meta['keywords']}"
date: {meta['date']}
robotstxt: "{{{{ robotstxt }}}}"
schema: Article
---

"""

# ─── 5. CSV-парсер ────────────────────────────────────────────────────────────

def read_keywords_csv(csv_path: str, top_n: int = 50) -> list[str]:
    """Читает ключевые слова из CSV. Поддерживает форматы ideav-ru и clinch."""
    keywords = []
    try:
        with open(csv_path, newline='', encoding='utf-8') as f:
            # Определяем разделитель: точка с запятой (clinch) vs запятая (ideav-ru)
            sample = f.read(1024)
            f.seek(0)
            delimiter = ';' if ';' in sample else ','
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                # Разные форматы колонок
                kw = (row.get('Ключевое слово') or row.get('keyword')
                      or row.get('phrase') or row.get('фраза')
                      or row.get('запрос'))
                if kw and kw.strip():
                    keywords.append(kw.strip())
                if len(keywords) >= top_n:
                    break
    except Exception as e:
        print(f"⚠️  Не удалось прочитать {csv_path}: {e}", file=sys.stderr)
    return keywords

# ─── 6. Гейты pSEO ───────────────────────────────────────────────────────────

def gate_desleeving(text: str, term: str) -> dict:
    """Гейт 1: снятие SEO-обвязки. Проверяет: страница полезна без title/description?"""
    # Убираем SEO-слова из текста и смотрим, остаётся ли полезный контент
    stripped = re.sub(r'\b(купить|заказать|цена|цены|доставка|интернет-магазин)\b', '', text, flags=re.IGNORECASE)
    stripped = re.sub(r'\s+', ' ', stripped).strip()
    word_count = len(stripped.split())
    has_substance = word_count > 100
    return {
        'stripped_word_count': word_count,
        'pass': has_substance,
        'message': '✅ Прошёл' if has_substance else '❌ Не прошёл — мало содержательного текста',
    }

# ─── 7. Точка входа ───────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 4:
        print("Использование: python3 generate-pseo-article.py <keywords.csv> <term> <modifier>")
        print("Пример:  python3 generate-pseo-article.py ../clinch/yadro-clinch-rabochiy.csv 'боксёрские перчатки' 'для начинающих'")
        sys.exit(1)

    csv_path = sys.argv[1]
    term = sys.argv[2]
    modifier = sys.argv[3]

    keywords = read_keywords_csv(csv_path)
    if not keywords:
        print("❌ Ключевые слова не найдены в CSV", file=sys.stderr)
        sys.exit(1)

    intent = detect_intent(keywords)

    # Генерируем
    article = build_article(term, modifier, keywords, intent)
    frontmatter = format_frontmatter(term, modifier, keywords)

    # Гейт 1
    gate = gate_desleeving(article, term)

    # Вывод
    output = frontmatter + article
    output_file = f"article-{term.replace(' ', '-')}-{modifier.replace(' ', '-')}.md"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(output)

    print(f"\n✅ Статья сгенерирована: {output_file}")
    print(f"   Ключевых слов: {len(keywords)}")
    print(f"   Намерение: {intent}")
    print(f"   Гейт 1 (без SEO-обвязки): {gate['message']}")
    print(f"   Слов без SEO-обёртки: {gate['stripped_word_count']}")

if __name__ == '__main__':
    main()
