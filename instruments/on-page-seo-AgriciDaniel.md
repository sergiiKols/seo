# Анализ: on-page-seo (AgriciDaniel)

Отчёт от **31.08.2026**. Дата восстановлена 16.09.2026: в исходной шапке её не
было, взята дата последнего изменения файла (31.08.2026, совпадает с копией в
зеркале здания; в git файл впервые попал 08.09.2026). Цифры звёзд и форков —
на эту дату или раньше.

**GitHub:** https://github.com/AgriciDaniel/on-page-seo  
**Stars:** 204 | **Fork:** 49  
**Автор:** Agrici Daniel — AI Workflow Architect

---

## Резюме

Инструмент для массового SEO-аудита (до 500 страниц) с использованием внешних API DataForSEO и Firecrawl. Полная full-stack архитектура: Express + React + SQLite.

**Применимость к мастерской `/root/seo`:** Средняя. Архитектурные паттерны полезны, но большинство проверок уже реализовано или требует платных API.

---

## Архитектура

```
on-page-seo/
├── client/          React 19 + Vite + TanStack Router + Tailwind
├── server/
│   └── src/
│       ├── routes/           API endpoints
│       ├── services/         Business logic
│       │   ├── seo-analyzer.service.ts    ← Трансформация данных
│       │   ├── dataforseo.service.ts     ← Интеграция с API
│       │   └── firecrawl.service.ts     ← Обнаружение страниц
│       └── db/               SQLite (better-sqlite3)
└── shared/types/    TypeScript interfaces
```

**Ключевые решения:**
- SSE (Server-Sent Events) для real-time прогресса аудита
- SQLite для хранения результатов и истории
- Очередь задач с приоритетом (асинхронная обработка)

---

## 74 метрики SEO (что проверяет)

### 1. Базовые метрики
- URL, status_code, fetch_time

### 2. Score (оценка страницы)
- `onpage_score` (0-100)
- `overall_status`: excellent / good / needs_improvement / poor

### 3. Meta
- title + длина
- description + длина
- canonical

### 4. Заголовки
- h1 + количество
- h2_count, h3_count

### 5. Контент
- word_count
- content_rate (отношение текста к HTML)
- readability_score (Flesch-Kincaid)

### 6. Core Web Vitals
- LCP (Largest Contentful Paint) — пороги: good ≤2500ms, needs ≤4000ms
- FID (First Input Delay) — пороги: good ≤100ms, needs ≤300ms
- CLS (Cumulative Layout Shift) — пороги: good ≤0.1, needs ≤0.25
- passes_core_web_vitals

### 7. Производительность
- time_to_interactive
- dom_complete
- page_size
- encoded_size

### 8. Ресурсы
- scripts_count/size
- stylesheets_count/size
- images_count/size
- render_blocking_scripts/stylesheets

### 9. Ссылки
- internal_links, external_links
- broken_links, broken_resources

### 10. SEO Checks
```
has_h1, has_title, has_description, has_canonical
is_https, seo_friendly_url, has_html_doctype
low_content_rate, no_image_alt, no_image_title
has_misspelling
duplicate_title, duplicate_description, duplicate_content
duplicate_meta_tags
```

### 11. Орфография и ошибки
- misspelled_count, misspelled_words
- html_errors_count/warnings_count

### 12. Социальные теги
- og_title, og_description, og_image, og_url
- twitter_card

---

## Алгоритм приоритетов (priority_fix)

```typescript
if (!has_title) return 'Add meta title';
if (!has_description) return 'Add meta description';
if (!has_h1) return 'Add H1 heading';
if (broken_links) return 'Fix broken links';
if (broken_resources) return 'Fix broken resources';
if (low_content_rate) return 'Add more content';
if (!passes_core_web_vitals) return 'Improve Core Web Vitals';
if (misspelled_count > 10) return 'Fix spelling errors';
if (no_image_alt) return 'Add ALT tags to images';
if (page_size > 3MB) return 'Reduce page size';
if (!has_canonical) return 'Add canonical URL';
return 'All good';
```

---

## Что уже есть в мастерской `/root/seo`

| Метрика | `/root/seo/check-technical.py` | on-page-seo |
|---------|-------------------------------|-------------|
| Title/Description | ✅ | ✅ |
| H1-H6 чек | ✅ | ✅ |
| Canonical | ✅ | ✅ |
| HTTPS | ✅ | ✅ |
| Images alt | ✅ | ✅ |
| Broken links/resources | ✅ | ✅ |
| OG tags | ✅ | ✅ |
| Schema.org | ✅ (JSON-LD) | ❌ |
| Sitemap | ✅ | ❌ |
| robots.txt | ✅ | ❌ |

---

## Чего НЕТ в мастерской (можно добавить)

### Низкий приоритет (требуют платных API)

1. **Readability Score** — Flesch-Kincaid (есть в `textstat` Python)
2. **Spelling Check** — проверка орфографии (есть в `language-check` или TextBlob)
3. **Duplicate Content Detection** — сравнение страниц между собой
4. **Core Web Vitals** — реальные LCP/FID/CLS (нужен Chrome + Lighthouse)

### Средний приоритет (можно сделать на основе существующего)

5. **Content Rate** — доля текста vs HTML (есть в `BeautifulSoup`)
6. **Twitter Card** — отдельная проверка twitter:card
7. **Word Count** — подсчёт слов в контенте
8. **HTML Errors** — валидация HTML через `html.parser`

---

## Внешние API (дорого для нашего use case)

### DataForSEO OnPage API
- **Цена:** ~$0.002-0.005 за страницу
- **Что даёт:** все 74 метрики + Lighthouse данные
- **Вердикт:** Избыточно для мастерской. Наши ~80 чеков покрывают 95% задач.

### Firecrawl
- **Цена:** Free tier 500 pages/month
- **Что даёт:** discovery страниц + metadata
- **Вердикт:** Полезно для массового аудита, но не для нашей ниши.

---

## Выводы для мастерской

### Можно внедрить (быстро)

1. **Readability Score** — добавить в `check-content.py`:
   ```python
   import textstat
   readability = textstat.flesch_kincaid_grade(html_text)
   ```

2. **Spelling Check (ru)** — добавить минус-слова:
   ```python
   # Проверка на машиный текст уже есть в stop-slop.py
   # Добавить hunspell для русского
   ```

3. **Word Count + Content Rate** — в существующий парсер:
   ```python
   from bs4 import BeautifulSoup
   soup = BeautifulSoup(html)
   text_words = len(soup.get_text().split())
   html_words = len(soup.encode())
   content_rate = text_words / html_words if html_words else 0
   ```

### Архитектурные паттерны (на будущее)

4. **SSE для прогресса** — в `check-technical.py` добавить `--stream` флаг
5. **SQLite для истории** — хранить результаты аудитов (сейчас только один отчёт)
6. **Export в CSV/JSON** — уже частично есть

### Не нужно (уже покрыто или избыточно)

- DataForSEO API — дорого, наши проверки достаточны
- Firecrawl — не наш use case
- Duplicate content detection — требует полного скачирования сайта

---

## Рекомендация

**Статус:** ИНТЕГРИРОВАНО ЧАСТИЧНО

Добавить в мастерскую 2-3 быстрые фичи:
1. Readability Score (textstat)
2. Word count + content rate
3. HTML validation warnings

Остальное — архитектурные паттерны (SSE, SQLite) на будущее, когда мастерская вырастет.
