# Мастерская SEO — карта задач

> Задача определяет маршрут. Инструменты выбираются под задачу.

---

## Конвейер: от ядра до GEO-видимости

```
Семантика (Задача 2)
    ↓  CSV ядра с разметкой интентов
Контент (Задача 3)
    ↓  опубликованные страницы
GEO-мониторинг (Задача 5)
    ↓  LLM Visibility Score
Анализ конкурентов (Задача 4) ← тоже получает GEO-слой
```

GEO-проверка — **не изолированная задача, а сквозной фильтр.** Она работает
на выходе контента и на входе конкурентного анализа. Если GEO-score падает —
возврат к контенту (Задача 3).

---

## Задача 1: Аудит сайта
**Вход:** URL сайта клиента  
**Выход:** `report.md` + `report.json` + `screenshots/`

```
URL → crawler → checker (80+ проверок) → scorer (0-100) → отчёт
```

**Скрипты:**
- `scripts/crawl-site.py` ✅ — HTTP-запрос + парсинг
- `scripts/check-technical.py` ✅ — 80+ проверок
- `scripts/score-audit.py` ✅ — взвешенная оценка 0-100

**Гейты:**
- Оценка < 50 → «требует вмешательства»
- Оценка 50–75 → «есть что улучшать»
- Оценка > 75 → «хорошее состояние»

---

## Задача 2: Семантическое ядро
**Вход:** URL каталога или список товаров  
**Выход:** `yadro-<проект>.csv`

```
Категории → Wordstat scraper → сбор ядра → разметка интентов → сверка дубликатов
```

**Скрипты:**
- `clinch/sobrat-yadro.py` — сбор из Wordstat
- `clinch/razmetit-yadro.py` — разметка интентов (branded / comparing / informing / commercial)
- `clinch/sverit-yadra.py` — сверка дубликатов

**Разметка интентов обязательна.** Без неё GEO-проверка не работает — не из чего
строить репрезентативную выборку для Задачи 5.

**Гейты:**
- Фраза встречается > 3 раз → проверить дубликат
- Намерение «нецелевое» → отфильтровать

**Выход для Задачи 5:** CSV с колонками `query,intent` — фильтровать через:
```bash
python3 -c "
import csv, sys
for row in csv.DictReader(sys.stdin):
    if row.get('intent') in ('branded','comparing','informing'):
        print(f\"{row['query']},{row.get('intent','any')}\")
" < yadro.csv > queries_for_geo.csv
```

---

## Задача 3: Контент по ядру
**Вход:** CSV ядра + term + modifier  
**Выход:** `.md` статья с frontmatter

```
CSV ядра → generate-pseo-article.py → humanize → stop-slop → GEO-чек → публикация
```

**Скрипты:**
- `scripts/generate-pseo-article.py` ✅ — генерация по шаблону + типографика
- `scripts/humanize-text.py` ✅ — стилизация под человека
- `scripts/humanize-ai.py` ✅ — очистка English AI-паттернов
- `scripts/stop-slop.py` ✅ — очистка от воды
- `scripts/add-schema.py` ✅ — JSON-LD разметка

**Гейты:**
- Гейт 1: снятие SEO-обвязки — страница осталась полезной?
- Гейт 2: сжатие в изложение — что потерялось? (Replaceability Test)
- Гейт 3: GEO-проверка (Задача 5) — страница попала в LLM-ответ?

**После публикации:** запустить Задачу 5 по опубликованным URL.
Результат записать в `geo-visibility.md` рядом со статьёй.

---

## Задача 4: Анализ конкурентов
**Вход:** SERP или URL конкурентов  
**Выход:** `konkurenty.md`

```
URL конкурента → рендер + анализ контента → сравнение с ядром → GEO-слой конкурентов → стратегия
```

**GEO-слой:** проверить видимость конкурентов в LLM по тем же запросам
через Задачу 5. Это даёт ответ: конкурент уже в LLM или нет.

**Гейты:**
- Конкурент сильнее по > 50% ядра → «нужен отдельный план»
- Конкурент слаб в GEO → «точка роста»
- GEO-score конкурента > нашего → «нанять отставание»

---

## Задача 5: GEO-мониторинг ✅
**Вход:** бренд + URL + CSV запросов (из Задачи 2)  
**Выход:** `geo-results.json` + `geo-visibility.md`

```
CSV запросов (branded/comparing/informing) → geo-rank-check → LLM Visibility Score → отчёт
```

**Инструмент:** скилл `geo-rank-check`:

```bash
# Быстрый старт — без GEOrank
python3 .claude/skills/geo-rank-check/scripts/geo_check.py \
  --mode direct \
  --brand "Бренд" \
  --url "https://site.ru" \
  --queries-file queries_for_geo.csv \
  --providers perplexity openai \
  --output geo-results.json

# GEOrank API (покрывает ChatGPT, Perplexity, GigaChat, ЯндексGPT сразу)
python3 .claude/skills/geo-rank-check/scripts/geo_check.py \
  --mode georank \
  --api-key $GEORANK_API_KEY \
  --brand "Бренд" \
  --queries-file queries_for_geo.csv \
  --output geo-results.json
```

**Три режима по бюджету:**

| Режим | Провайдеры | Стоимость | Когда |
|---|---|---|---|
| `--mode direct` + `perplexity` | Perplexity Sonar | бесплатно (100/день) | Первая проверка, разовый аудит |
| `--mode direct` + `perplexity openai` | Sonar + GPT-4o-mini | бесплатно/~$0.01 | Сравнение моделей |
| `--mode georank` | ChatGPT + Perplexity + ЯндексGPT + GigaChat | от 20 000 ₽/мес | Регулярный мониторинг |

**Гейты:**

| LLM Visibility Score | Значение | Действие |
|---|---|---|
| 0–20 | Критический | Срочно: проверить индексацию, усилить внешний след |
| 21–40 | Слабый | Сфокус на Comparing, усилить E-E-A-T |
| 41–65 | Средний | Работать с Comparing/Informing, повторять каждые 4 недели |
| 66–80 | Хороший | Мониторить ежемесячно |
| 81–100 | Отличный | Следить за контекстом (позитив/негатив) |

**Повторять:** каждые 4 недели. Один срез ≠ динамика. Для одной точки замера —
`--runs 5` в `geo_check.py`: APR по запросам, порог стабильности 20%
(`instruments/apr-citing-2026-09.md`).

**Ряд замеров и три числа** (v1.4.0, `instruments/seo-04-ai-tri-imeni.md`):

```bash
python3 .claude/skills/geo-rank-check/scripts/geo_check.py \
  --brand "Бренд" --url "https://site.ru" \
  --anchors Новосибирск "веб-разработка" \
  --queries-file queries_for_geo.csv \
  --history geo-history.jsonl --output geo-results.json
```

- `--history` — прогон дописывается в ряд и сравнивается с прошлым; сравнение
  только при совпадении отпечатка (набор запросов + провайдеры).
- `--anchors` — слова, подтверждающие, что назвали именно нас; без них
  упоминания уходят в спорные и в балл не входят.
- В отчёт идут три числа: присутствие, назвали по имени, взяли как источник.
  Плюс «источником без имени» — наш ответ работает, узнаваемости ноль.

---

## Задача 6: Перенос сайта без потери позиций

**Вход:** старый сайт и новая версия (новый домен, новая структура URL или и то
и другое)
**Выход:** карта адресов + маршрутный лист переезда

```
карта старый→новый URL → 301 постранично → панели поиска → sitemap → наблюдение недели-месяцы
```

**Правила:** `instruments/seo-05-perenos-sayta.md` — 20 пунктов по справкам
Google и Яндекса. Коротко, что ломает переезд чаще всего: редирект всего на
главную, цепочки редиректов, `noindex` или запрет в robots.txt на новой версии,
несовпадающее содержимое версий, совмещение переезда с редизайном.

**Статус:** правила прочитаны, практикой не проверены — переездов мастерская не
делала. Живой кандидат рядом: `clinch` (переезд в `/root/clinch-migration`).
Скрипт проверки переезда появится на первом живом переезде, а не раньше.

---

## Структура мастерской

```
/root/seo/
├── scripts/              ← Скрипты для автоматизации
├── skills/              ← Скиллы (.claude/skills/ и skills/)
│   ├── yandex-direct/
│   ├── google-ads/
│   └── geo-rank-check/   ← GEO-мониторинг
├── instruments/          ← Разборы инструментов и источников
├── clinch/              ← Проект-гость: clinch.by
├── ideav-ru/            ← Проект-гость: ideav.ru
├── MAP.md               ← Эта карта
└── README.md            ← Описание мастерской
```

---

## Скрипты

| Файл | Задача | Статус |
|------|--------|--------|
| `generate-pseo-article.py` | Контент | ✅ Готово |
| `crawl-site.py` | Аудит | ✅ Готово |
| `score-audit.py` | Аудит | ✅ Готово |
| `check-technical.py` | Аудит | ✅ Готово (v2.0, Health/Coverage) |
| `render_page.py` | Инфраструктура | ✅ SPA-ready |
| `url_safety.py` | Безопасность | ✅ SSRF Protection |
| `sobrat-yadro.py` | Семантика | ✅ Есть (clinch) |
| `razmetit-yadro.py` | Семантика | ✅ Есть (clinch) |
| `sverit-yadra.py` | Семантика | ✅ Есть (clinch) |
| `humanize-ai.py` | Контент | ✅ English AI Patterns |
| `humanize-text.py` | Контент | ✅ Готово |
| `stop-slop.py` | Контент | ✅ Готово |
| `add-schema.py` | Контент | ✅ Готово |

---

## Скиллы

| Скилл | Назначение | Режим |
|---|---|---|
| `yandex-direct` | Яндекс.Директ из ядра | CSV → объявления |
| `google-ads` | Google Ads (RSA) из ядра | CSV → RSA |
| `geo-rank-check` | GEO-видимость в LLM | CSV + бренд → Score |

**geo-rank-check — как запустить быстро:**
```bash
# 1. Фильтруем ядро для GEO
grep -E "branded|comparing|informing" yadro.csv > queries_for_geo.csv

# 2. GEO-чек
python3 .claude/skills/geo-rank-check/scripts/geo_check.py \
  --mode direct --brand "Бренд" --url "https://site.ru" \
  --queries-file queries_for_geo.csv -o geo-results.json

# 3. Читаем score
python3 -c "
import json
d = json.load(open('geo-results.json'))
print(f\"LLM Visibility Score: {d['llm_visibility_score']}/100\")
for k, v in d['summary'].items():
    if isinstance(v, dict):
        print(f\"  {k}: {v['found']}/{v['total']} ({v['visibility']}%)\")
"
```

---

## Как завести новую задачу

1. Создать папку проекта: `/root/<проект>/`
2. Определить тип задачи (1–5)
3. Выбрать нужные скрипты и скиллы
4. Запустить → результат в папке проекта
5. Проверить гейты
6. **GEO-слой:** после Задачи 3 (контент) — запустить Задачу 5 по опубликованным URL

**Правило:** задача не считается закрытой, пока не прошла все гейты.
