# Перелинковка базы знаний ideav.ru — карта, дыры, рекомендации

Дата: **18.08.2026**. Периметр — 35 страниц: главная, 7 продуктовых,
страница-индекс `knowledge-base.html` и 27 статей `knowledge-base/<slug>.html`.
Метод: сырой `curl`-HTML всех 35 страниц + отрендеренный DOM (Playwright,
1440×900, `networkidle` + 2 с) на **13** страницах (10 статей базы знаний,
главная, индекс раздела, 7 продуктовых — итого 19 рендеров) + разбор
`src/data/knowledgeBase.ts` и **боевого** чанка данных
`https://ideav.ru/assets/knowledgeBase-DhgKfoSd.js` (все 27 статей, включая
те три, которых нет в локальном репозитории).

---

## 0. Диагноз одной фразой

**Внутри базы знаний — плотная сеть; наружу, к продуктовым страницам, —
чистая звезда через общее меню.** 27 статей связаны между собой 115
работающими ссылками (в среднем 4,3 входящих на статью, 29 взаимных пар), но
на профильную продуктовую страницу ведут **2 статьи из 27**. Всё остальное
сообщение «база знаний → продукт» идёт только через шапку и подвал, то есть
для поисковика это шаблонная навигация, а не тематический сигнал.

---

## 1. Находка №1: сырой HTML и отрендеренный DOM расходятся

Это не техническая деталь, а прямая потеря ссылок, поэтому идёт первым
пунктом.

**Что видит краулер без JS (сырой HTML статьи):**
логотип → `/`, хлебная крошка → `/knowledge-base.html`,
CTA «Загрузите Excel — получите приложение →» → `/excel-to-app.html`,
3–5 «Похожих статей», «← Все статьи базы знаний». Всего 7–9 внутренних
ссылок. **Ни шапки, ни подвала, ни стрелок «предыдущая/следующая» в сыром
HTML нет вообще.**

**Что видит браузер (после гидратации):** шапка (16 ссылок) + подвал (18) +
«предыдущая/следующая» + блок «Источники» + «Смежные статьи». 42–49 ссылок.
**Но при этом хлебная крошка и CTA на `excel-to-app.html` из тела страницы
исчезают.**

Проверено напрямую (`document.body.innerText` и `page.content()` после
гидратации):

| Страница | ссылка | в сыром HTML | в DOM после JS |
|---|---|:---:|:---:|
| `knowledge-base/01-…` | CTA «Загрузите Excel — получите приложение →» → `/excel-to-app.html` | есть | **нет** |
| `knowledge-base/21-…` | то же | есть | **нет** |
| любая статья | хлебная крошка «База знаний» | есть | **нет** |
| `tokens.html` | → `/knowledge-base/16-pricing-policy.html` | есть | **нет** |
| главная | «База знаний» → `/knowledge-base` в теле | есть | **нет** |
| `excel-to-app.html` | «База знаний» → `/knowledge-base` в теле | есть | **нет** |
| `agent-platforms.html` | «база знаний» | `/knowledge-base` | `/knowledge-base.html` |

Причина видна по репозиторию: пререндер статей собран из ветки
`seo/kb-interlinking-breadcrumbs-cta` (коммит 6c45e08 «SEO: prerendered KB
articles — breadcrumbs, related links, CTA»), а отдаваемый бандл
`index-Dx4b-LKo.js` — из другой сборки. Пререндер и клиентский код
рассинхронизированы: React при гидратации затирает разметку, которой в его
дереве нет.

**Следствие.** Единственная ссылка «статья → продукт», существующая на всех
27 статьях (CTA на `excel-to-app.html`), работает только для краулеров без
JS. Живой посетитель и Googlebot после рендера её не видят. То же с
`tokens.html → 16-pricing-policy`.

Побочно: `/knowledge-base` отдаёт 301 на `/knowledge-base/`, а тот — 200 с
тем же содержимым, что и `/knowledge-base.html` (canonical правильный, ведёт
на `.html`). Три URL на один документ; в пререндере продуктовых страниц
ссылки идут на бесканоничный вариант `/knowledge-base`.

---

## 2. Матрица связей: входящие и исходящие по каждой странице

«Сыро» — по `curl`-HTML. «Рендер» — по DOM после JS (включая шапку и подвал).
«Контекст. вх» — входящие **без** шапки, подвала и индекса раздела, то есть
только осмысленные редакционные ссылки; именно эта колонка показывает
реальную структуру.

| Страница | сыро вх | сыро исх | рендер вх | рендер исх | контекст. вх | откуда контекстные входящие |
|---|--:|--:|--:|--:|--:|---|
| `главная` | 34 | 11 | 35 | 16 | 2 | excel-to-app, konstruktor-prilozhenij |
| `sravnenie-s-bitrix-amocrm` | 0 | 2 | 35 | 8 | 0 | — |
| `excel-to-app` | 31 | 3 | 35 | 8 | 4 | agent-platforms, informatsionnaya-sistema, konstruktor-prilozhenij, главная |
| `konstruktor-prilozhenij` | 1 | 4 | 35 | 8 | 1 | главная |
| `agent-platforms` | 7 | 3 | 35 | 8 | 2 | excel-to-app, главная |
| `catalog-matching` | 2 | 3 | 35 | 9 | 3 | 21-catalog-matching, konstruktor-prilozhenij, главная |
| `tokens` | 1 | 3 | 35 | 8 | 1 | главная |
| `informatsionnaya-sistema` | 1 | 5 | 35 | 9 | 3 | 22-information-system-constructor, konstruktor-prilozhenij, главная |
| `knowledge-base` | 31 | 27 | 35 | 35 | 29 | 01-google-sheets-150k, 02-excel-row-limit, 03-excel-file-versions, 04-related-tables, 05-access-rights, 06-airtable-control, 07-notion-relational-data, 08-html-templates, 08a-vibe-coding-templates, 09-custom-development-prototype, 10-no-release-changes, 11-ai-interface-data-safety, 12-ai-prototype-rewrite, 13-api-json-export, 14-forms, 14a-reports, 14b-dashboards, 15-local-control-files, 16-pricing-policy, 17-smart-google-import, 18-on-premise-procurement, 19-ai-agent-app-build, 20-semantic-memory-without-vector-db, 21-catalog-matching, 22-information-system-constructor, 23-security-fault-tolerance, 24-pure-business-design, agent-platforms, informatsionnaya-sistema |
| `01-google-sheets-150k` | 7 | 8 | 7 | 15 | 6 | 02-excel-row-limit, 03-excel-file-versions, 04-related-tables, 05-access-rights, 17-smart-google-import, 21-catalog-matching |
| `02-excel-row-limit` | 4 | 6 | 5 | 12 | 3 | 03-excel-file-versions, 04-related-tables, главная |
| `03-excel-file-versions` | 5 | 7 | 5 | 13 | 4 | 01-google-sheets-150k, 02-excel-row-limit, 04-related-tables, 05-access-rights |
| `04-related-tables` | 10 | 7 | 12 | 14 | 10 | 01-google-sheets-150k, 02-excel-row-limit, 03-excel-file-versions, 07-notion-relational-data, 14-forms, 17-smart-google-import, 20-semantic-memory-without-vector-db, 21-catalog-matching, 22-information-system-constructor, главная |
| `05-access-rights` | 14 | 8 | 16 | 15 | 14 | 01-google-sheets-150k, 03-excel-file-versions, 06-airtable-control, 07-notion-relational-data, 10-no-release-changes, 11-ai-interface-data-safety, 13-api-json-export, 14-forms, 14b-dashboards, 15-local-control-files, 18-on-premise-procurement, 22-information-system-constructor, 23-security-fault-tolerance, главная |
| `06-airtable-control` | 9 | 8 | 9 | 15 | 8 | 05-access-rights, 07-notion-relational-data, 08-html-templates, 13-api-json-export, 16-pricing-policy, 18-on-premise-procurement, 20-semantic-memory-without-vector-db, главная |
| `07-notion-relational-data` | 5 | 7 | 6 | 14 | 4 | 01-google-sheets-150k, 04-related-tables, 05-access-rights, 08-html-templates |
| `08-html-templates` | 6 | 8 | 7 | 14 | 5 | 06-airtable-control, 08a-vibe-coding-templates, 10-no-release-changes, 11-ai-interface-data-safety, 15-local-control-files |
| `08a-vibe-coding-templates` | 3 | 7 | 4 | 14 | 2 | 08-html-templates, 24-pure-business-design |
| `09-custom-development-prototype` | 4 | 8 | 5 | 15 | 3 | 10-no-release-changes, 12-ai-prototype-rewrite, 19-ai-agent-app-build |
| `10-no-release-changes` | 6 | 7 | 6 | 14 | 5 | 09-custom-development-prototype, 11-ai-interface-data-safety, 12-ai-prototype-rewrite, 19-ai-agent-app-build, главная |
| `11-ai-interface-data-safety` | 5 | 7 | 6 | 13 | 4 | 08-html-templates, 08a-vibe-coding-templates, 12-ai-prototype-rewrite, 19-ai-agent-app-build |
| `12-ai-prototype-rewrite` | 8 | 7 | 8 | 13 | 7 | 08a-vibe-coding-templates, 09-custom-development-prototype, 10-no-release-changes, 11-ai-interface-data-safety, 13-api-json-export, 19-ai-agent-app-build, 24-pure-business-design |
| `13-api-json-export` | 12 | 7 | 13 | 14 | 11 | 06-airtable-control, 07-notion-relational-data, 12-ai-prototype-rewrite, 14a-reports, 14b-dashboards, 15-local-control-files, 16-pricing-policy, 17-smart-google-import, 18-on-premise-procurement, 21-catalog-matching, 23-security-fault-tolerance |
| `14-forms` | 6 | 7 | 7 | 14 | 5 | 09-custom-development-prototype, 14a-reports, 14b-dashboards, 15-local-control-files, 16-pricing-policy |
| `14a-reports` | 8 | 7 | 9 | 13 | 8 | 09-custom-development-prototype, 13-api-json-export, 14-forms, 14b-dashboards, 17-smart-google-import, 20-semantic-memory-without-vector-db, 21-catalog-matching, главная |
| `14b-dashboards` | 4 | 7 | 5 | 14 | 3 | 09-custom-development-prototype, 14-forms, 14a-reports |
| `15-local-control-files` | 8 | 8 | 9 | 16 | 7 | 06-airtable-control, 08-html-templates, 08a-vibe-coding-templates, 16-pricing-policy, 18-on-premise-procurement, 20-semantic-memory-without-vector-db, 23-security-fault-tolerance |
| `16-pricing-policy` | 3 | 7 | 4 | 14 | 1 | 22-information-system-constructor |
| `17-smart-google-import` | 3 | 7 | 5 | 15 | 2 | 01-google-sheets-150k, 21-catalog-matching |
| `18-on-premise-procurement` | 6 | 7 | 8 | 15 | 5 | 06-airtable-control, 15-local-control-files, 22-information-system-constructor, 23-security-fault-tolerance, главная |
| `19-ai-agent-app-build` | 3 | 7 | 5 | 15 | 2 | 22-information-system-constructor, 24-pure-business-design |
| `20-semantic-memory-without-vector-db` | 2 | 7 | 4 | 15 | 1 | 14a-reports |
| `21-catalog-matching` | 2 | 8 | 4 | 16 | 1 | catalog-matching |
| `22-information-system-constructor` | 3 | 8 | 5 | 16 | 2 | 24-pure-business-design, informatsionnaya-sistema |
| `23-security-fault-tolerance` | 2 | 7 | 5 | 15 | 2 | 05-access-rights, главная |
| `24-pure-business-design` | 1 | 7 | 2 | 14 | 0 | — |

**Как читать.** В колонке «рендер вх» у главной, семи продуктовых и индекса
стоит 35 — это шапка и подвал, они есть на каждой странице периметра. Ноль
информации о тематической близости эта цифра не несёт. Реальная картина — в
колонке «контекст. вх».

Структура исходящих у статьи одинакова у всех 27: шапка (8 внутренних
ссылок периметра) + подвал (5, из них `tokens.html` только тут) + индекс
раздела + 3–5 «Смежных статей» + «предыдущая/следующая». Разброс 12–16
исходящих объясняется только числом смежных статей и наличием стрелок.

---

## 3. Механизм `relatedSlugs` — заполнен, но замкнут сам на себя

Штатное поле связей заполнено у **27 статей из 27**, всего объявлено **118**
рёбер. Интерфейс показывает максимум 5 «Смежных статей», поэтому реально
работают **115**: статья `09-custom-development-prototype` теряет 6-ю связь
(`05-access-rights`), `15-local-control-files` — 6-ю и 7-ю (`14a-reports`,
`14b-dashboards`). Списки в сыром HTML и в DOM после рендера совпадают
дословно — этот блок гидратацию переживает.

Распределение входящих по `relatedSlugs`:

- **Хабы:** `05-access-rights` (13), `13-api-json-export` (11),
  `04-related-tables` (9), `06-airtable-control` / `12-ai-prototype-rewrite` /
  `14a-reports` / `15-local-control-files` (по 7).
- **Ноль входящих:** `21-catalog-matching`, `24-pure-business-design` — их не
  указал в `relatedSlugs` никто.
- **Одна входящая:** `16-pricing-policy`, `20-semantic-memory-without-vector-db`,
  `22-information-system-constructor`, `23-security-fault-tolerance`.

Взаимных пар — 29 из 115 связей (25%), то есть граф заметно
однонаправленный. Хуже другое: **ни одно значение `relatedSlugs` не ведёт за
пределы базы знаний** — механизм по устройству умеет связывать только
статьи со статьями. Все 27 статей ссылаются наружу ровно через три канала:
меню, индекс раздела и (у двух статей) блок `sources`.

---

## 4. Сироты и тупики

**Сироты — ноль контекстных входящих (меню, подвал и индекс раздела не в
счёт):**

1. **`sravnenie-s-bitrix-amocrm.html`** — 0 контекстных входящих и **0
   входящих в сыром HTML вообще** по всему периметру. Для краулера без JS
   это недостижимая страница. Рекомендация №1 отчёта от 05.08 («главная →
   сравнение») закрыта только пунктом меню «Больше CRM»: в теле главной
   ссылки на неё по-прежнему нет.
2. **`knowledge-base/24-pure-business-design.html`** — 0 контекстных
   входящих. Достижима только из индекса раздела и стрелкой «предыдущая» с
   `23-security-fault-tolerance`. При этом сама статья — про фирменный
   подход Pure Business Design, то есть коммерчески одна из самых ценных.

**Почти-сироты (одна контекстная входящая):** `konstruktor-prilozhenij.html`
и `tokens.html` (только с главной), `21-catalog-matching` (только с
`catalog-matching.html`, ни одной с других статей), `16-pricing-policy`
(только с 22), `20-semantic-memory-without-vector-db` (только с 14a).

**Тупики — страницы, не ведущие дальше ничем, кроме общего меню:**

1. **`tokens.html`** — 0 контекстных исходящих в периметре (в теле только
   внешняя ссылка на ActivTrak и `start.html`). Ссылка на профильную статью
   `16-pricing-policy` есть только в пререндере и пропадает после
   гидратации — см. раздел 1.
2. **`sravnenie-s-bitrix-amocrm.html`** — 0 контекстных исходящих в
   периметре (ведёт на `crm-uchet-klientov.html` и `resheniya.html`, они вне
   периметра). Полный тупик: и не получает, и не отдаёт.
3. **`excel-to-app.html`** — 2 контекстных исходящих (главная,
   `agent-platforms.html`), **ни одной ссылки ни на одну статью базы
   знаний**, хотя все 27 статей исторически на него указывали.
4. **`agent-platforms.html`** — 2 контекстных исходящих
   (`excel-to-app.html` и индекс базы знаний), ни одной статьи.
5. **`knowledge-base.html`** — 27 ссылок вниз, на статьи, и **ноль ссылок на
   продуктовые страницы**. Индекс раздела работает как односторонний
   распределитель веса.

---

## 5. Глубина клика от главной

Считалось два способа.

**А. С учётом общего меню (то, что видит браузер).** Все 35 страниц
достижимы, максимум — 2 клика: главная → 8 продуктовых/индекс (1 клик) → 27
статей (2 клика). Восемь статей достижимы за 1 клик прямо с главной:
`02-excel-row-limit`, `04-related-tables`, `05-access-rights`,
`06-airtable-control`, `10-no-release-changes`, `14a-reports`,
`18-on-premise-procurement`, `23-security-fault-tolerance`.

**Б. Только по контекстным ссылкам, без меню и подвала** — то, как
распределяется вес и как ходит читатель по смыслу:

| Глубина | Статей | Кто |
|---|--:|---|
| 1 клик | 8 | 02, 04, 05, 06, 10, 14a, 18, 23 (ссылки в теле главной) |
| 2 клика | 13 | достижимы через «Смежные статьи» первых восьми |
| 3 клика | 6 | `08a-vibe-coding-templates`, `11-ai-interface-data-safety`, `16-pricing-policy`, `17-smart-google-import`, `19-ai-agent-app-build`, `24-pure-business-design` |

С учётом стрелок «предыдущая/следующая» на глубине 3 остаются только
`08a-vibe-coding-templates` и `16-pricing-policy`.

**В сыром HTML** (без JS) картина хуже: `sravnenie-s-bitrix-amocrm.html`
недостижима вовсе, а с главной за 1 клик видны лишь 4 статьи (02, 06, 10, 18).

---

## 6. Главная дыра: статьи ↔ профильные продуктовые страницы

Проверено по боевому чанку данных: во всех 27 статьях на продуктовые
страницы ideav.ru ведут ровно **две** ссылки, обе — внутри блока `sources`
(«Источники»):

- `21-catalog-matching` → `https://ideav.ru/catalog-matching.html`
  («Страница инструмента «Массовое сопоставление каталогов»»);
- `22-information-system-constructor` → `https://ideav.ru/informatsionnaya-sistema.html`.

Третья ссылка наружу — `16-pricing-policy` → `start.html#tarif` — ведёт на
страницу вне периметра, а на профильную `tokens.html` не ведёт.

| # | Статья | Профильная продуктовая страница | Ссылка есть? |
|---|---|---|:---:|
| 01 | google-sheets-150k | `excel-to-app.html` | нет (только CTA в пререндере) |
| 02 | excel-row-limit | `excel-to-app.html` | нет (только CTA в пререндере) |
| 03 | excel-file-versions | `excel-to-app.html` | нет (только CTA в пререндере) |
| 04 | related-tables | `konstruktor-prilozhenij.html` | **нет** |
| 05 | access-rights | `informatsionnaya-sistema.html` | **нет** |
| 06 | airtable-control | `konstruktor-prilozhenij.html` | **нет** |
| 07 | notion-relational-data | `konstruktor-prilozhenij.html` | **нет** |
| 08 | html-templates | `konstruktor-prilozhenij.html` | **нет** |
| 08a | vibe-coding-templates | `agent-platforms.html` | **нет** |
| 09 | custom-development-prototype | `agent-platforms.html` | **нет** |
| 10 | no-release-changes | `konstruktor-prilozhenij.html` | **нет** |
| 11 | ai-interface-data-safety | `agent-platforms.html` | **нет** |
| 12 | ai-prototype-rewrite | `agent-platforms.html` | **нет** |
| 13 | api-json-export | `informatsionnaya-sistema.html` | **нет** |
| 14 | forms | `konstruktor-prilozhenij.html` | **нет** |
| 14a | reports | `konstruktor-prilozhenij.html` | **нет** |
| 14b | dashboards | `konstruktor-prilozhenij.html` | **нет** |
| 15 | local-control-files | `informatsionnaya-sistema.html` | **нет** |
| 16 | pricing-policy | `tokens.html` | **нет** (только `start.html#tarif`) |
| 17 | smart-google-import | `excel-to-app.html` | нет (только CTA в пререндере) |
| 18 | on-premise-procurement | `informatsionnaya-sistema.html` | **нет** |
| 19 | ai-agent-app-build | `agent-platforms.html` | **нет** |
| 20 | semantic-memory-without-vector-db | `agent-platforms.html` | **нет** |
| 21 | catalog-matching | `catalog-matching.html` | **да** (`sources`) |
| 22 | information-system-constructor | `informatsionnaya-sistema.html` | **да** (`sources`) |
| 23 | security-fault-tolerance | `informatsionnaya-sistema.html` | **нет** |
| 24 | pure-business-design | `agent-platforms.html` | **нет** |

**Итог: 25 статей из 27 не связаны со своей профильной продуктовой
страницей.** У четырёх (01, 02, 03, 17) профиль совпадает с общим CTA на
`excel-to-app.html`, но он живёт только в пререндере.

Обратное направление симметрично дырявое: из семи продуктовых страниц на
конкретные статьи ссылаются только две (`catalog-matching.html` → 21,
`informatsionnaya-sistema.html` → 22). `sravnenie-s-bitrix-amocrm.html` —
единственная продуктовая страница, у которой нет ни одной темы-пары в базе
знаний вообще.

---

## 7. Рекомендации

Формат: **откуда → куда**, анкор, точное место вставки в терминах полей
`KnowledgeBaseArticle` (`context`, `scenario`, `integramScenario`,
`integramDifference`, `limitations`, `conclusion`, `sources`,
`relatedSlugs`) и соответствующих им заголовков на странице: `context` →
«Контекст», `scenario` → «Конкретный сценарий», `integramScenario` → «Тот же
сценарий в Интеграме», `integramDifference` → «Что делает Интеграм иначе»,
`limitations` → «Ограничения Интеграма в этом сценарии», `conclusion` →
«Вывод», `sources` → «Источники», `relatedSlugs` → «Смежные статьи».

### 7.1. Сначала — почини гидратацию (иначе половина работы уйдёт в никуда)

**Р0.** Пересобрать и выложить фронтенд так, чтобы пререндер и бандл были из
одной сборки. Сейчас на 27 статьях в браузере теряются хлебная крошка и CTA
на `excel-to-app.html`, а на `tokens.html` — ссылка на `16-pricing-policy`.
Пока это не сделано, любая новая ссылка, добавленная только в пререндер,
будет исчезать после гидратации, а любая ссылка, добавленная в
`knowledgeBase.ts`, не попадёт в пререндер. Проверка после выката: на
`https://ideav.ru/knowledge-base/01-google-sheets-150k.html` фраза «Загрузите
Excel» должна присутствовать в `document.body.innerText`.

### 7.2. Пять самых дорогих ссылок

**Р1. `19-ai-agent-app-build` → `agent-platforms.html`.**
Статья дословно про то, что продаёт страница «Платформы с ИИ-агентами», и
при этом у неё всего 2 контекстных входящих и глубина 3 клика.
*Куда:* последний шаг массива `integramScenario.steps` («Тот же сценарий в
Интеграме») — добавить шаг со ссылкой; плюс продублировать в `conclusion`.
*Анкор:* «чем сборка приложения агентом Интеграма отличается от зарубежных
и российских агентских платформ».
*Обратно:* на `agent-platforms.html` в блоке «Ещё сравнения — в базе знаний
→» заменить ссылку на индекс раздела на прямую ссылку в статью с анкором
«как ИИ-агент собирает приложение: пошаговый разбор».

**Р2. `16-pricing-policy` ↔ `tokens.html`.**
Единственная пара «статья про цену — страница про цену», и она разорвана в
обе стороны: у статьи в `sources` стоит `start.html#tarif`, а на `tokens.html`
ссылка на статью существует только в пререндере. `tokens.html` — тупик с
нулём контекстных исходящих, статья — глубина 3 клика и одна входящая.
*Куда (статья):* массив `sources` — добавить пункт «Токены: как считается
стоимость работы ИИ-агента» → `https://ideav.ru/tokens.html`; плюс в
`conclusion` фразой «сколько токенов уходит на типовые операции».
*Куда (страница):* блок с итоговой стоимостью на `tokens.html`, рядом с
существующим CTA «Начать работу» — «почему в Интеграме нет платы за место в
таблице и за каждого пользователя →».

**Р3. `24-pure-business-design` — вытащить из сирот.**
0 контекстных входящих, никто не указал её в `relatedSlugs`, при этом это
статья о фирменном методе проектирования.
*Куда:* добавить `'24-pure-business-design'` в `relatedSlugs` статей
`09-custom-development-prototype`, `19-ai-agent-app-build` и
`08a-vibe-coding-templates` — все три про «как рождается приложение», и все
три уже ссылаются друг на друга.
*Плюс:* в `limitations` статьи `08a-vibe-coding-templates` («Ограничения
Интеграма в этом сценарии»), где речь про рукописные шаблоны, — ссылка с
анкором «проектирование от описания задачи, а не от блоков и кубиков».
*Наружу:* сама статья → `agent-platforms.html`, анкор «чем это отличается от
режима «сгенерируй мне приложение» у ИИ-платформ», место — `conclusion`.

**Р4. `sravnenie-s-bitrix-amocrm.html` — единственная страница периметра с
нулём входящих и нулём исходящих.**
В сыром HTML на неё не ведёт вообще ничего; в меню она спрятана под пунктом
«Больше CRM».
*Куда 1:* в теле главной, в блоке «Готовые типы проектов» рядом с карточкой
«CRM и системы учёта клиентов» — ссылка «сравнение с Битрикс24 и AmoCRM →»
(рекомендация №1 от 05.08, до сих пор не выполнена в теле страницы).
*Куда 2:* в `limitations` статьи `22-information-system-constructor` — там
уже говорится о границе с коробочными ИС; анкор «если задача укладывается в
коробочную CRM — вот разбор Битрикс24 и AmoCRM».
*Куда 3:* обратно со страницы сравнения — в её FAQ, вопрос про перенос
данных, ссылка на `05-access-rights` с анкором «права доступа по ролям без
редакции коробки».

**Р5. Группа «конструктор» — 7 статей → `konstruktor-prilozhenij.html`.**
Самая массивная дыра по весу: `04-related-tables` (10 контекстных входящих),
`06-airtable-control` (8), `14a-reports` (8), `14-forms` (5),
`08-html-templates` (5), `10-no-release-changes` (5), `14b-dashboards` (3) —
суммарно 44 входящих сигнала, которые никуда дальше не передаются.
*Куда:* в `integramDifference` («Что делает Интеграм иначе») каждой из семи
— один пункт со ссылкой; анкоры разные, по теме статьи:
- 04 → «реляционные связи в конструкторе Интеграма»;
- 06 → «российский конструктор с собственным контуром вместо Airtable»;
- 08 → «свои HTML-шаблоны поверх конструктора»;
- 10 → «правки структуры без релиза в конструкторе»;
- 14 → «формы, которые пишут прямо в базу»;
- 14a → «отчёты на тех же данных без выгрузок»;
- 14b → «дашборды на тех же данных».
*Обратно:* на `konstruktor-prilozhenij.html` уже есть FAQ-вопрос «Чем это
отличается от услуги «Загрузите Excel — получите приложение»?» — рядом
добавить вопрос «Что будет с моими отчётами и правами доступа?» со ссылками
на `14a-reports` и `05-access-rights`.

### 7.3. Остальные дыры «статья → профиль» (список для одного прохода)

Одна ссылка на статью, в поле `conclusion` («Вывод») последним предложением,
если не указано иное.

| Статья | Куда | Анкор | Поле |
|---|---|---|---|
| 01 | `excel-to-app.html` | «загрузить выгрузку из Google Sheets и получить приложение» | `conclusion` |
| 02 | `excel-to-app.html` | «перенести накопленный Excel-реестр в базу за один заход» | `integramScenario` |
| 03 | `excel-to-app.html` | «одна база вместо рассылки файлов — как перенести» | `conclusion` |
| 05 | `informatsionnaya-sistema.html` | «роли и права как часть информационной системы» | `integramDifference` |
| 07 | `konstruktor-prilozhenij.html` | «реляционная база в конструкторе вместо связанных баз Notion» | `conclusion` |
| 08a | `agent-platforms.html` | «чем агент Интеграма отличается от вайб-кодинга в чате» | `limitations` |
| 09 | `agent-platforms.html` | «прототип силами агента вместо команды разработки» | `integramScenario` |
| 11 | `agent-platforms.html` | «почему AI в Интеграме не трогает данные, а только интерфейс» | `integramDifference` |
| 12 | `agent-platforms.html` | «доработка приложения тем же агентом, без переписывания» | `conclusion` |
| 13 | `informatsionnaya-sistema.html` | «API как контур интеграции информационной системы» | `integramDifference` |
| 15 | `informatsionnaya-sistema.html` | «развёртывание в собственном контуре заказчика» | `limitations` |
| 17 | `excel-to-app.html` | «умный импорт таблицы в готовое приложение» | `integramScenario` |
| 18 | `informatsionnaya-sistema.html` | «информационная система в реестре отечественного ПО» | `conclusion` |
| 20 | `agent-platforms.html` | «память по смыслу внутри агентской платформы Интеграма» | `conclusion` |
| 23 | `informatsionnaya-sistema.html` | «требования к отказоустойчивости корпоративной ИС» | `integramDifference` |

### 7.4. Дыры внутри базы знаний (`relatedSlugs`)

1. **`21-catalog-matching` не указана ни в одной статье.** Добавить в
   `relatedSlugs`: `04-related-tables`, `17-smart-google-import`,
   `13-api-json-export` — все три она сама уже указывает, связь станет
   взаимной.
2. **`20-semantic-memory-without-vector-db`** (1 входящая) — добавить в
   `relatedSlugs` статей `19-ai-agent-app-build` и `13-api-json-export`.
3. **`16-pricing-policy`** (1 входящая) — добавить в `relatedSlugs` статей
   `06-airtable-control` и `15-local-control-files` (обе про стоимость
   владения; обе уже указаны у 16).
4. **`23-security-fault-tolerance`** (1 входящая из статей) — добавить в
   `relatedSlugs` статей `18-on-premise-procurement` и `15-local-control-files`.
5. **`22-information-system-constructor`** (1 входящая из статей) — добавить
   в `relatedSlugs` статей `05-access-rights` и `18-on-premise-procurement`.
6. **Потери на капе.** Интерфейс режет список до 5: у
   `09-custom-development-prototype` не показывается `05-access-rights`, у
   `15-local-control-files` — `14a-reports` и `14b-dashboards`. Либо поднять
   лимит до 7, либо переставить эти слаги в начало массива.

### 7.5. Индекс раздела и обратный ход с продуктовых

1. **`knowledge-base.html` → продуктовые.** Индекс отдаёт 27 ссылок вниз и
   ноль вбок. Разбить список на тематические группы и над каждой поставить
   ссылку на профильную страницу: «Excel и таблицы» → `excel-to-app.html`,
   «Конструктор и интерфейсы» → `konstruktor-prilozhenij.html`, «ИИ-агенты» →
   `agent-platforms.html`, «Информационная система, контур, безопасность» →
   `informatsionnaya-sistema.html`, «Стоимость» → `tokens.html`.
2. **`excel-to-app.html` → база знаний.** Сейчас в теле нет ни одной ссылки
   на статьи (в пререндере есть бесканоничная `/knowledge-base`). В блоке
   FAQ, где речь про объём загружаемых данных, — ссылка на
   `02-excel-row-limit` с анкором «что делать с листом, упершимся в 1 048 576
   строк», и на `17-smart-google-import` с анкором «как импортируется
   таблица из Google Sheets».
3. **`konstruktor-prilozhenij.html`** — уже ведёт на `catalog-matching.html`
   и `informatsionnaya-sistema.html`, но ни на одну статью. Добавить пару из
   Р5 (14a, 05).
4. **Единый URL индекса.** В пререндере продуктовых заменить
   `/knowledge-base` на канонический `/knowledge-base.html`, чтобы не
   разводить вес по трём адресам одного документа.

---

## 8. Что померено и чем

- Сырой HTML всех 35 страниц: `curl -sS`, 18.08.2026, все 200.
- Отрендеренный DOM: Playwright/Chromium 1440×900, `networkidle` + 2000 мс,
  сбор всех `a[href]` с разметкой зоны (`header` / `nav` / `footer` / `body`).
  Страницы: 01, 02, 08a, 14b, 16, 19, 21, 22, 23, 24, главная,
  `knowledge-base.html` и все 7 продуктовых.
- Данные статей: `src/data/knowledgeBase.ts` (локально — 24 статьи, ветка
  `seo/kb-interlinking-breadcrumbs-cta`) и боевой чанк
  `/assets/knowledgeBase-DhgKfoSd.js` (27 статей). **Локальный репозиторий
  отстаёт от продакшена на три статьи (22, 23, 24) — их нет ни в `main`, ни
  в рабочей ветке.** Правки по этому отчёту нужно вносить в источник, из
  которого собран продакшен.
