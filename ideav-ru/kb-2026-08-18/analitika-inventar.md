# База знаний ideav.ru — инвентарь 27 статей

Дата снимка: 18.08.2026.
Источники: `/root/backlogram/src/data/knowledgeBase.ts` (24 статьи) + опубликованный чанк
`https://ideav.ru/assets/knowledgeBase-DhgKfoSd.js` (все 27, включая `22`, `23`, `24`, которых в репозитории нет).
Инвентарь построен по **опубликованным** данным: они являются надмножеством репозитория.

## Расхождения репозитория и продакшена (важно перед правками)

Живой сайт новее локального репозитория в трёх местах — правки в репозитории эти изменения затрут, если не подтянуть их сначала:

| статья | что расходится |
|---|---|
| `05-access-rights` | `relatedSlugs` на сайте другой |
| `07-notion-relational-data` | на сайте появились `seoTitle`, `seoDescription`, `ogTitle`, `ogDescription` и блок `integramScenario` — в репозитории их нет |
| `21-catalog-matching` | на сайте другой состав `sources` |

Статьи `22-information-system-constructor`, `23-security-fault-tolerance`, `24-pure-business-design` в репозитории отсутствуют целиком.
Их `sourceUrl` ведёт не в `ideav/crm/docs`, как у остальных, а на issue в `ideav/backlogram` (#490, #426 и т. п.).

## Таблица

| slug | № | title (полный) | compare | seoTitle | seoDescription (длина) | metaDescription (длина) | metaKeywords, фраз | слов в статье | заполненные необязательные блоки | relatedSlugs |
|---|---|---|---|---|---|---|---|---|---|---|
| `01-google-sheets-150k` | 01 | 150 000 записей без ручного хаоса: когда Интеграм удобнее Google Sheets | Google Sheets | НЕТ | НЕТ | НЕТ | НЕТ | 378 | scenario(4) | 17-smart-google-import, 04-related-tables, 05-access-rights, 03-excel-file-versions, 07-notion-relational-data |
| `02-excel-row-limit` | 02 | Нет потолка одного листа Excel: как Интеграм помогает уйти от лимита 1 048 576 строк | Excel | НЕТ | НЕТ | да (182) | 11 | 556 | scenario(4); IDD(4); sources(1) | 01-google-sheets-150k, 03-excel-file-versions, 04-related-tables |
| `03-excel-file-versions` | 03 | Единая версия данных вместо десятков файлов: почему Интеграм надежнее Excel-рассылок | Excel и локальные файлы | НЕТ | НЕТ | да (236) | 10 | 663 | scenario(4); IDD(4) | 02-excel-row-limit, 05-access-rights, 04-related-tables, 01-google-sheets-150k |
| `04-related-tables` | 04 | Связанные таблицы без ВПР и ручных справочников: чем Интеграм сильнее таблиц | Excel и Google Sheets | НЕТ | НЕТ | да (275) | 13 | 645 | scenario(4); IDD(4) | 01-google-sheets-150k, 02-excel-row-limit, 03-excel-file-versions, 07-notion-relational-data |
| `05-access-rights` | 05 | Права доступа из коробки: почему Интеграм безопаснее общей таблицы | Excel, Google Sheets, простые no-code-таблицы | НЕТ | НЕТ | да (271) | 12 | 740 | scenario(5); IDD(5); limitationsNote | 23-security-fault-tolerance, 03-excel-file-versions, 01-google-sheets-150k, 06-airtable-control, 07-notion-relational-data |
| `06-airtable-control` | 06 | Собственный контур вместо SaaS-зависимости: чем Интеграм привлекательнее Airtable | Airtable | НЕТ | НЕТ | да (264) | 11 | 900 | scenario(6); IDD(6); limitationsNote; sources(2) | 15-local-control-files, 18-on-premise-procurement, 08-html-templates, 13-api-json-export, 05-access-rights |
| `07-notion-relational-data` | 07 | Реляционная база вместо доски заметок: где Интеграм практичнее Notion | Notion | да | да (243) | да (248) | 10 | 802 | scenario(4); integramScenario(6); IDD(6); sources(2) | 04-related-tables, 05-access-rights, 13-api-json-export, 06-airtable-control |
| `08-html-templates` | 08 | HTML-шаблоны вместо закрытого интерфейса: как Интеграм дает больше гибкости no-code-сервисов | Airtable Interfaces, Notion views и другие закрытые конструкторы интерфейсов | да | да (255) | да (377) | 11 | 813 | scenario(4); IDD(6) | 08a-vibe-coding-templates, 06-airtable-control, 07-notion-relational-data, 11-ai-interface-data-safety, 15-local-control-files |
| `08a-vibe-coding-templates` | 08a | Вайб-кодинг рабочих мест для Интеграма: как сгенерировать шаблон ИИ и вставить его в main.html | вайб-кодинг рабочих мест и ручная вёрстка шаблонов | да | да (221) | да (240) | 14 | 1485 | scenario(6); integramScenario(6); flowDiagram(4); IDD(10); limitationsNote; sources(5) | 08-html-templates, 11-ai-interface-data-safety, 12-ai-prototype-rewrite, 15-local-control-files |
| `09-custom-development-prototype` | 09 | Готовое приложение быстрее заказной разработки: как Интеграм сокращает путь от идеи до прототипа | заказная разработка | да | НЕТ | НЕТ | НЕТ | 516 | scenario(5); integramScenario(5); limitationsList(4); limitationsNote | 10-no-release-changes, 12-ai-prototype-rewrite, 14-forms, 14a-reports, 14b-dashboards, 05-access-rights |
| `10-no-release-changes` | 10 | Изменения без нового релиза: почему Интеграм дешевле поддерживать, чем заказную систему | заказная разработка | да | да (135) | НЕТ | НЕТ | 422 | scenario(5) | 09-custom-development-prototype, 12-ai-prototype-rewrite, 08-html-templates, 05-access-rights |
| `11-ai-interface-data-safety` | 11 | AI помогает интерфейсу, но не ломает данные: чем Интеграм надежнее вайб-кодинга | вайб-кодинг (генерация приложений через ИИ) | да | да (153) | НЕТ | НЕТ | 570 | scenario(6); IDD(4) | 12-ai-prototype-rewrite, 08-html-templates, 05-access-rights, 10-no-release-changes |
| `12-ai-prototype-rewrite` | 12 | Без переписывания с нуля после первого демо: где Интеграм практичнее вайб-кодинга | вайб-кодинг и быстрые AI-прототипы | да | да (170) | НЕТ | НЕТ | 697 | scenario(5); IDD(6) | 11-ai-interface-data-safety, 09-custom-development-prototype, 10-no-release-changes, 13-api-json-export |
| `13-api-json-export` | 13 | API и JSON-экспорт вместо копипаста: как Интеграм связывает учет с внешними системами | Excel, Google Sheets, Notion, ручные выгрузки | да | да (120) | НЕТ | 10 | 648 | scenario(4); flowDiagram(4); IDD(4); limitationsList(3); limitationsNote | 05-access-rights, 06-airtable-control, 14a-reports, 12-ai-prototype-rewrite |
| `14-forms` | 14 | Формы рядом с данными: чем Интеграм удобнее связки Google Forms + Google Sheets + Zapier | Google Forms + Google Sheets + Zapier | да | да (142) | да (165) | 10 | 609 | scenario(4); IDD(7) | 14a-reports, 14b-dashboards, 05-access-rights, 04-related-tables |
| `14a-reports` | 14a | Отчёты на той же базе: чем Интеграм удобнее связки Google Sheets + Looker Studio | Google Sheets + Looker Studio, Excel + Power BI | да | да (140) | да (172) | 9 | 593 | scenario(4); IDD(8) | 14-forms, 14b-dashboards, 13-api-json-export, 20-semantic-memory-without-vector-db |
| `14b-dashboards` | 14b | Дашборды на тех же данных: чем Интеграм удобнее связки таблицы и внешнего BI | Looker Studio, Power BI, Metabase, Tableau | да | да (142) | да (177) | 10 | 586 | scenario(4); IDD(10) | 14-forms, 14a-reports, 13-api-json-export, 05-access-rights |
| `15-local-control-files` | 15 | Локально, с доступами и своими файлами: почему Интеграм подходит компаниям с требованиями к контролю | облачные no-code-сервисы и внешний подряд | да | да (158) | НЕТ | 9 | 619 | scenario(6); IDD(5) | 18-on-premise-procurement, 05-access-rights, 08-html-templates, 13-api-json-export, 14-forms, 14a-reports, 14b-dashboards |
| `16-pricing-policy` | 16 | Тарифы в токенах, а не «за пользователя»: чем тарифная политика Интеграма отличается от Airtable, Notion и Google Workspace | Airtable, Notion, Google Workspace и другие SaaS | да | да (223) | да (208) | 10 | 929 | scenario(4); flowDiagram(4); IDD(6); limitationsList(3); limitationsNote; sources(7) | 14-forms, 15-local-control-files, 06-airtable-control, 13-api-json-export |
| `17-smart-google-import` | 17 | Умный импорт из Google Sheets: синхронизация по разрезам, а не по координатам ячеек | Google Sheets, CSV и ручной импорт | да | да (177) | да (183) | 12 | 940 | scenario(5); flowDiagram(4); IDD(8); limitationsList(4); limitationsNote; sources(6) | 01-google-sheets-150k, 04-related-tables, 13-api-json-export, 14a-reports |
| `18-on-premise-procurement` | 18 | On-premise в реестре Минцифры: docker-разворот, импортозамещение и корпоративная авторизация | зарубежные SaaS и закрытые корпоративные платформы без российской прописки | да | да (184) | да (167) | 12 | 836 | scenario(6); IDD(6); limitationsList(4); limitationsNote; sources(2) | 15-local-control-files, 06-airtable-control, 05-access-rights, 13-api-json-export |
| `19-ai-agent-app-build` | 19 | Приложение собирает ИИ-агент: чем подход Интеграма отличается от программистов и готовых коробок | заказная разработка и готовые SaaS-коробки | да | НЕТ | да (254) | 12 | 913 | scenario(3); integramScenario(5); IDD(4); sources(1) | 09-custom-development-prototype, 12-ai-prototype-rewrite, 11-ai-interface-data-safety, 10-no-release-changes |
| `20-semantic-memory-without-vector-db` | 20 | Память по смыслу без отдельной базы: рекурсия и графы в Интеграме | Векторные и графовые СУБД (pgvector, Neo4j, Pinecone) | НЕТ | НЕТ | НЕТ | НЕТ | 541 | scenario(4); limitationsList(3); sources(2) | 14a-reports, 04-related-tables, 15-local-control-files, 06-airtable-control |
| `21-catalog-matching` | 21 | Сопоставление каталогов на сотни тысяч позиций: Интеграм вместо Elasticsearch и кода | Elasticsearch | НЕТ | НЕТ | НЕТ | НЕТ | 649 | scenario(4); integramScenario(5); IDD(5); limitationsList(3); sources(3) | 17-smart-google-import, 04-related-tables, 13-api-json-export, 14a-reports, 01-google-sheets-150k |
| `22-information-system-constructor` | 22 | Информационная система на low-code с ИИ вместо заказной разработки | Заказная разработка и коробочные ИС | да | да (182) | да (252) | 10 | 618 | scenario(4); integramScenario(5); limitationsList(3); sources(2) | 19-ai-agent-app-build, 04-related-tables, 05-access-rights, 18-on-premise-procurement, 16-pricing-policy |
| `23-security-fault-tolerance` | 23 | Безопасность и отказоустойчивость: данные крупного бизнеса под контролем | закрытый облачный SaaS без контроля инфраструктуры | НЕТ | НЕТ | да (266) | 13 | 941 | scenario(5); IDD(5); limitationsList(3) | 05-access-rights, 15-local-control-files, 18-on-premise-procurement, 13-api-json-export |
| `24-pure-business-design` | 24 | Pure Business Design: приложение по описанию задачи, без блоков и кубиков | визуальные no-code конструкторы и ИИ-ассистенты в режиме human-in-the-loop | да | да (277) | да (274) | 11 | 1383 | scenario(5); integramScenario(6); IDD(6); limitationsList(4); sources(1) | 19-ai-agent-app-build, 22-information-system-constructor, 12-ai-prototype-rewrite, 08a-vibe-coding-templates |

## Подсчёты

### seoDescription

- **Нет `seoDescription` у 11 из 27** статей: `01-google-sheets-150k`, `02-excel-row-limit`, `03-excel-file-versions`, `04-related-tables`, `05-access-rights`, `06-airtable-control`, `09-custom-development-prototype`, `19-ai-agent-app-build`, `20-semantic-memory-without-vector-db`, `21-catalog-matching`, `23-security-fault-tolerance`.
  У них описание для выдачи собирается фолбэком `seoDescription → metaDescription → summary`
  (`src/pages/KnowledgeBaseArticle.tsx`, строка 77), то есть в сниппет уходит либо длинный `metaDescription`,
  либо ещё более длинный `summary` — обрезается почти всегда.
- **Длиннее 160 символов — 9 статей** (обрежется в выдаче): `07-notion-relational-data` (243), `08-html-templates` (255), `08a-vibe-coding-templates` (221), `12-ai-prototype-rewrite` (170), `16-pricing-policy` (223), `17-smart-google-import` (177), `18-on-premise-procurement` (184), `22-information-system-constructor` (182), `24-pure-business-design` (277).
- **Короче 80 символов — 0 статей.** Недобора нет ни у одной.
- **В коридоре 80–160 символов — только 7 статей** из 27: `10-no-release-changes`, `11-ai-interface-data-safety`, `13-api-json-export`, `14-forms`, `14a-reports`, `14b-dashboards`, `15-local-control-files`.

### Прочие мета-поля

- **Нет `seoTitle` у 9 статей**: `01-google-sheets-150k`, `02-excel-row-limit`, `03-excel-file-versions`, `04-related-tables`, `05-access-rights`, `06-airtable-control`, `20-semantic-memory-without-vector-db`, `21-catalog-matching`, `23-security-fault-tolerance`. Без него `pageTitle` собирается как `«shortTitle — База знаний — Интеграм»`.
- **Нет `metaDescription` у 9 статей**: `01-google-sheets-150k`, `09-custom-development-prototype`, `10-no-release-changes`, `11-ai-interface-data-safety`, `12-ai-prototype-rewrite`, `13-api-json-export`, `15-local-control-files`, `20-semantic-memory-without-vector-db`, `21-catalog-matching`.
- **Нет `metaKeywords` у 7 статей**: `01-google-sheets-150k`, `09-custom-development-prototype`, `10-no-release-changes`, `11-ai-interface-data-safety`, `12-ai-prototype-rewrite`, `20-semantic-memory-without-vector-db`, `21-catalog-matching`. У остальных — от 9 до 14 фраз (медиана 11).
- Длина `metaDescription` там, где он есть: от 165 до 377 символов — **ни один не укладывается в 160**;
  это поле изначально писалось не под сниппет.

### Ссылочная связность и источники

- **Пустых `relatedSlugs` — 0.** Все 27 статей ссылаются на соседей: от 3 до 7 слагов, у 18 статей ровно 4.
- **Нет `sources` у 15 из 27** статей: `01-google-sheets-150k`, `03-excel-file-versions`, `04-related-tables`, `05-access-rights`, `08-html-templates`, `09-custom-development-prototype`, `10-no-release-changes`, `11-ai-interface-data-safety`, `12-ai-prototype-rewrite`, `13-api-json-export`, `14-forms`, `14a-reports`, `14b-dashboards`, `15-local-control-files`, `23-security-fault-tolerance`.
  У остальных 12 — от 1 до 7 источников (в сумме 34 ссылки).

### Объём

- Суммарно ~19992 слов текста статьи (без мета-полей), в среднем **740 слов** на статью.
- Самые короткие: `01-google-sheets-150k` (378), `10-no-release-changes` (422), `09-custom-development-prototype` (516).
- Самые длинные: `08a-vibe-coding-templates` (1485), `24-pure-business-design` (1383), `23-security-fault-tolerance` (941).
- 16 статей короче 700 слов — это ниже типичного объёма конкурентной выдачи по коммерческим запросам.

### Наполненность необязательных блоков

| блок | сколько статей из 27 | у кого |
|---|---|---|
| `scenario` (боль клиента + симптомы) | **27** | у всех |
| `integramDifference` (главный список отличий) | **27** | у всех, 3–8 пунктов |
| `integramDifferenceDetailed` (развёрнутые отличия) | 22 | нет у `01`, `09`, `10`, `20`, `22` |
| `integramScenario` (пошаговый сценарий на Интеграме) | 7 | `07`, `08a`, `09`, `19`, `21`, `22`, `24` |
| `flowDiagram` (схема потока) | **4** | `08a`, `13`, `16`, `17` |
| `limitationsList` (ограничения списком) | 10 | `09`, `13`, `16`, `17`, `18`, `20`, `21`, `22`, `23`, `24` |
| `limitationsNote` | 8 | `05`, `06`, `08a`, `09`, `13`, `16`, `17`, `18` |
| `sources` | 12 | см. выше |

Побочная находка: `limitationsNote` у `13`, `16` и `17` написан не для читателя, а для автора —
это редакторские заметки, попавшие в опубликованный текст. Пример из `16-pricing-policy`:
«В статье не стоит утверждать, что Интеграм всегда дешевле Airtable, Notion или Google Workspace».
Читатель видит это на странице.

## Таблицы и блоки «вопрос — ответ»: подтверждено, их нет

Проверено тремя способами:

1. **Схема данных** (`KnowledgeBaseArticle` в `knowledgeBase.ts`, строки 34–61) не содержит ни одного поля
   под таблицу или под пару «вопрос — ответ». Всё содержимое — строки, массивы строк и объекты
   `{title, body}` / `{intro, steps}`.
2. **Рендерер** `/root/backlogram/src/pages/KnowledgeBaseArticle.tsx` (525 строк) не выводит ни `<table>`,
   ни `<dl>`, ни аккордеон. JSON-LD собирается как `TechArticle` + `BreadcrumbList` — **`FAQPage` не генерируется**.
3. **Тексты всех 27 статей**: разметки таблиц (`<table>`, markdown-пайпы, `---`) нет ни в одной.
   Единственный `|` в корпусе — внутри строки конфига в `17-smart-google-import` (`"ПЛАН||ФАКТ"`), не таблица.
   Вопросительных знаков в прозе — **один на все 27 статей** («Вопрос «где правда?»» в `14a-reports`);
   остальные `?` — это URL вида `report/{id}?json`.
   Восклицательных знаков в прозе — **ноль** (все `!` в корпусе — внутри HTML-комментариев `<!-- Begin:… -->`).

**Вывод: ни таблиц сравнения, ни FAQ в базе знаний нет вовсе.** Добавление любого из этих блоков
потребует расширения интерфейса `KnowledgeBaseArticle`, правки рендерера
`KnowledgeBaseArticle.tsx`, пререндера `scripts/prerender-knowledge-base.mjs`
и — для FAQ — добавления `FAQPage` в JSON-LD.
