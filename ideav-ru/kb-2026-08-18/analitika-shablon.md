# База знаний ideav.ru — анализ общего шаблона статьи

Дата: **18.08.2026**. Объект — не отдельная статья, а **общий шаблон**, по
которому собраны все **27** страниц раздела `/knowledge-base/*.html`.
Логика та же, что в продуктовом разделе: ищем дефекты, которые чинятся
одной правкой и закрывают весь раздел разом.

Метод — измерение, не чтение кода. Зонд `probe.mjs` (сырой `fetch`-HTML
отдельно, живой DOM через Playwright на 1440px и 768px отдельно) прогнан
на пяти разных по типу статьях; затем два сплошных прогона по всем 27
URL из `sitemap.xml` — `probe3.mjs` (сырой + отрендеренный) и сверка
JSON-LD/ссылок/картинок (`probe2.mjs`). Сырые JSON — в конце файла,
полные выгрузки: `sweep27.json`, `sweep27-rendered.json`.

Исходники, по которым объяснена причина каждой находки:
`src/pages/KnowledgeBaseArticle.tsx` (SPA-рендер и JSON-LD),
`scripts/prerender-knowledge-base.mjs` (пререндер для краулера),
`src/data/knowledgeBase.ts` (данные), `tests/knowledge-base-*.test.mjs`,
`tests/kb-article-*.test.mjs`.

---

## Главное одной строкой

**Раздел собирают два независимых рендерера одной и той же статьи, и они
не согласованы.** Пререндер (то, что видит краулер без JS) отдаёт
примерно треть текста, свой `<title>`, своё описание, свой JSON-LD типа
`TechArticle` и CTA на `/excel-to-app.html`. SPA (то, что видит человек)
дорисовывает остальные две трети текста, переписывает `<title>` и
`description`, добавляет **второй** JSON-LD типа `Article` со **вторым**
`BreadcrumbList` — и при этом **убирает CTA**. Из 8 находок ниже 5 —
прямое следствие этого расхождения.

---

## Сводная таблица находок

Порядок — по стоимости. «Охват» — сколько из 27 страниц задевает.

| # | Находка | Охват | Причина в коде (файл:строка) | Как чинить | Критерий приёмки |
|---|---|---|---|---|---|
| 1 | **61 % текста статьи отдаётся только после JS.** Сырой HTML — 9 052 слова на весь раздел, после гидратации — 23 425. Медиана сырой страницы 310 слов, диапазон 232–558. В пререндер не попадают блоки «Что делает Интеграм иначе» (`integramDifference` / `integramDifferenceDetailed`), «Ограничения Интеграма в этом сценарии» (`limitations`, `limitationsList`, `limitationsNote`), «Вывод» (`conclusion`), диаграмма процесса (`flowDiagram`) и «Источники» (`sources`) — то есть ровно тот дифференцирующий и E-E-A-T-контент, ради которого статья написана. По данным репозитория: 5 491 слово внутри пререндера против 11 798 снаружи = 68 % | 27 / 27 | `scripts/prerender-knowledge-base.mjs:433-452` — шаблон `articleBody` собирает только `summary`, `context`, `scenario`, `integramScenario`, CTA и «Похожие статьи». Полей `integramDifference*`, `limitations*`, `conclusion`, `flowDiagram`, `sources` в шаблоне нет вообще. Те же поля в SPA рисуются на `src/pages/KnowledgeBaseArticle.tsx:336-447` | Дописать в `articleBody` секции для всех перечисленных полей, в том же порядке и с теми же заголовками, что в SPA. Это тот же класс задачи, что №3 в `plan-rabot-2026-08-12.md` для `excel-to-app.html`, только ×27 страниц | На каждой из 27 страниц `curl` без JS отдаёт не менее **85 %** слов от отрендеренного DOM (сейчас 28–49 %), и в сыром HTML присутствуют подстроки «Ограничения», «Вывод», «Что делает Интеграм иначе» |
| 2 | **Три JSON-LD-блока на странице вместо одного, два из них конфликтуют.** После гидратации в `<head>` лежат: (а) пререндерный граф `TechArticle` + `BreadcrumbList`, (б) SPA-блок `Article`, (в) SPA-блок `BreadcrumbList`. То есть **две сущности статьи разного `@type` на один URL** и **два `BreadcrumbList`**. Плюс у них разный `publisher.logo`: `/logos/integram-og.png` в пререндере и `/favicon.ico` в SPA — `.ico` не годится как `ImageObject` логотипа и режет расширенные результаты | 27 / 27 | `src/pages/KnowledgeBaseArticle.tsx:57-61` — `clearJsonLd()` удаляет только `script[type="application/ld+json"][data-jsonld]`; у пререндерного блока атрибута `data-jsonld` нет, поэтому он остаётся. Дубли создаются на `:115-147` (`'@type': 'Article'`) и `:149-170` (`BreadcrumbList`). Логотип-иконка — `:143-145` | Оставить один источник разметки. Проще всего: в SPA не создавать `article`/`breadcrumb`, если в `<head>` уже есть блок без `data-jsonld`; либо помечать пререндерный блок `data-jsonld="prerender"`, чтобы `clearJsonLd()` его снимал. Тип согласовать (`TechArticle`), логотип — на `/logos/integram-og.png` | После полной загрузки `document.querySelectorAll('script[type="application/ld+json"]').length === 1` на всех 27; в нём ровно один узел с `@type` из семейства Article и ровно один `BreadcrumbList`; `publisher.logo.url` не оканчивается на `.ico`. **Внимание: противоречит существующим тестам** `tests/knowledge-base-jsonld.test.mjs` (проверяет `'@type': 'Article'` в SPA и что `clearJsonLd` ищет именно `[data-jsonld]`) — тесты надо править вместе с кодом |
| 3 | **`datePublished` нет ни на одной странице; `dateModified` = дате сборки.** Во всех 27 сырых HTML `dateModified: "2026-08-18"` — это `new Date()` в момент прогона сборки, одинаковая на всех статьях и меняющаяся при каждом деплое. В SPA-блоке `Article` дат нет вообще. При этом `sitemap.xml` для тех же URL отдаёт `lastmod 2026-05-13` — прямое противоречие внутри одного сайта | 27 / 27 | `scripts/prerender-knowledge-base.mjs:144` (`const todayISO = new Date().toISOString()...`), используется на `:361` (статья) и `:302` (индекс). В `src/data/knowledgeBase.ts` интерфейс `KnowledgeBaseArticle` (строки 34-60) **не содержит полей дат вообще** | Добавить в интерфейс `datePublished` и `dateModified`, проставить руками по каждой статье, брать их в пререндере вместо `todayISO`, синхронизировать с `lastmod` в `sitemap.xml`. Это задача №6 из `plan-rabot-2026-08-12.md`, распространённая на базу знаний | В JSON-LD каждой из 27 страниц оба поля заполнены; `dateModified` **не меняется** при повторной сборке без правки контента; `dateModified` статьи совпадает с её `lastmod` в `sitemap.xml` |
| 4 | **`description` расходится между сырым HTML и рендером на 23 из 27 страниц, `title` — на 16 из 27.** Причина — разный порядок приоритетов полей в двух рендерерах. Побочный эффект: в отрендеренной версии описание раздувается — **20 из 27** длиннее 160 символов (максимум 409), тогда как в сыром HTML длиннее 160 только 1 из 27. И 9 из 27 отрендеренных `<title>` длиннее 60 символов (до 85), в сыром — ни одного | 23 / 27 (desc), 16 / 27 (title) | Пререндер: `scripts/prerender-knowledge-base.mjs:340-341` — `seoTitle \|\| title` и `metaDescription \|\| seoDescription \|\| trim(summary,260)`. SPA: `src/pages/KnowledgeBaseArticle.tsx:76-77` — `seoTitle ?? \`${shortTitle} — База знаний — Интеграм\`` и `seoDescription ?? metaDescription ?? summary` (без обрезки). Порядок полей разный, фолбэки разные | Вынести вычисление `title`/`description` в один общий модуль и импортировать его и в пререндер, и в компонент. Заодно вернуть обрезку описания в SPA | На всех 27 страницах `<title>` и `<meta name="description">` в `curl` и в DOM после загрузки совпадают **дословно**; ни один `title` не длиннее 60 символов, ни один `description` — 160 |
| 5 | **CTA внутри статьи есть у краулера и отсутствует у человека.** В сыром HTML каждая статья заканчивается блоком «Из вашего Excel — рабочее приложение» с кнопкой на `/excel-to-app.html`. После гидратации этот блок исчезает: `article a[href*="excel-to-app"]` найден на **0 из 27** страниц. Живой посетитель дочитывает статью и не получает ни одной ссылки на конверсионную страницу — только «Смежные статьи» и «Предыдущая/Следующая» внутрь того же раздела | 27 / 27 | Блок описан только в пререндере: `scripts/prerender-knowledge-base.mjs:427-431`. В `src/pages/KnowledgeBaseArticle.tsx` аналога нет — после «Вывода» (`:405-417`) сразу идут «Источники» и «Смежные статьи» | Добавить тот же CTA-блок в компонент, сразу после секции «Вывод» | На всех 27 страницах после полной загрузки `document.querySelector('article a[href*="excel-to-app"]')` не `null` |
| 6 | **Слой H2 — шаблонная мебель без единого поискового слова.** Сырой HTML отдаёт 3–4 `<h2>` на страницу, и по частоте это: «Контекст» — 27 раз, «Из вашего Excel — рабочее приложение» — 27, «Похожие статьи» — 27, «Как это решает Интеграм» — 7. То есть из 3 заголовков две — служебные (CTA и блок ссылок), содержательный ровно один. После гидратации H2 становится 6–9, но набор тот же на всех 27: «Контекст», «Конкретный сценарий», «Тот же сценарий в Интеграме», «Что делает Интеграм иначе», «Ограничения Интеграма в этом сценарии», «Вывод», «Источники», «Смежные статьи». Ни одного вхождения предмета статьи. Вдобавок эти H2 отрисованы как `font-size: 12px; font-weight: 900; text-transform: uppercase; color: slate-400` — визуально это микро-подпись, а не заголовок; и H3 нет вообще (0 на 26 страницах из 27, 4 только у `08a`) | 27 / 27 | Тексты H2 захардкожены в компоненте: `src/pages/KnowledgeBaseArticle.tsx:240, 250, 281, 305, 337, 379, 408, 420, 451`. Класс одинаков во всех девяти местах. Часть тех же секций в пререндере названа **иначе** («Как это решает Интеграм» вместо «Тот же сценарий в Интеграме», «Похожие статьи» вместо «Смежные статьи») — `scripts/prerender-knowledge-base.mjs:395, 402, 416` | Сделать заголовки данными, а не константами: добавить в `KnowledgeBaseArticle` необязательные поля вида `sectionHeadings`, куда для каждой статьи кладётся заголовок с предметом («Ограничения Интеграма при 150 000 строк»). Фолбэк — текущий текст. Тексты пререндера и SPA взять из одного источника | На 27 страницах хотя бы **3** `<h2>` содержат слово из `metaKeywords` или из `compare` своей статьи; набор текстов H2 в сыром HTML и в DOM совпадает; ни один H2 не отрисован размером меньше 16px |
| 7 | **Нет ни `FAQPage`, ни `HowTo` — ни на одной из 27.** Проверено по всем сырым HTML: `FAQPage` не встречается нигде. При этом контент под них готов: у 24 статей есть `scenario.symptoms` (готовые «боли» → вопросы), у 4 — `integramScenario.steps`, у 4 — `flowDiagram.steps` (готовые пошаговые инструкции) | 27 / 27 | Схемы просто не собираются: в `scripts/prerender-knowledge-base.mjs:344-388` граф состоит только из `TechArticle` и `BreadcrumbList`; в `src/pages/KnowledgeBaseArticle.tsx:115-170` — только `Article` и `BreadcrumbList` | Собирать `FAQPage` из `scenario.symptoms` + соответствующих абзацев (нужно добавить в данные поле «ответ»), и `HowTo` — из `integramScenario.steps` / `flowDiagram.steps` там, где они есть | `FAQPage` присутствует минимум на 20 из 27 страниц и проходит валидатор Rich Results без ошибок; `HowTo` — на всех страницах, где заполнен `integramScenario` или `flowDiagram` |
| 8 | **Контентных изображений нет: единственная картинка на странице — та же OG-обложка.** На всех 27 в DOM ровно один `<img>` — `/og/<slug>.png`, 1200×630, `loading="eager"`, вес 133–142 КБ PNG, выводится сразу под H1 (то есть это LCP-элемент), `alt` шаблонный — «Обложка статьи: <shortTitle>». Ни схем, ни скриншотов интерфейса, ни таблиц-сравнений картинкой — при том что раздел целиком про сравнение инструментов | 27 / 27 | Обложка задаётся один раз в каждом рендерере: `src/pages/KnowledgeBaseArticle.tsx:226-236` и `scripts/prerender-knowledge-base.mjs:440-442`. Других изображений шаблон не предусматривает — в интерфейсе `KnowledgeBaseArticle` нет поля под иллюстрации | Добавить поле под иллюстрации с осмысленным `alt`, минимум по одной содержательной картинке (схема «до/после» или скриншот) на статью. Обложку отдавать в WebP/AVIF | На каждой из 27 страниц минимум 2 `<img>`, у всех непустой `alt`, ни один `alt` не начинается с «Обложка статьи»; вес LCP-картинки ≤ 60 КБ |
| 9 | **Разметка `BreadcrumbList` есть, видимых хлебных крошек после гидратации нет.** В сыром HTML крошки нарисованы («Интеграм › База знаний › <статья>»), в живом DOM их нет: `nav[aria-label*="рошк"]` не находится ни на одной из 5 проверенных | 27 / 27 | Крошки описаны только в пререндере: `scripts/prerender-knowledge-base.mjs:435-437`. В компоненте вместо них одна ссылка «← Все статьи базы знаний» (`src/pages/KnowledgeBaseArticle.tsx:200-205`) | Нарисовать крошки в компоненте тем же составом, что в разметке `BreadcrumbList` | На всех 27 страницах после загрузки в DOM есть видимый элемент с тремя уровнями крошек, тексты которых совпадают с `name` трёх `ListItem` в JSON-LD |
| 10 | **Из статьи не уходит ни одной ссылки в продуктовый кластер; в сыром HTML нет шапки и подвала сайта.** Сырая страница отдаёт **6–8 уникальных ссылок** всего: «/», «/knowledge-base.html», 3–5 статей раздела и ровно одна продуктовая — CTA на `/excel-to-app.html`. Общего меню сайта (14 пунктов, включая `/konstruktor-prilozhenij.html`, `/agent-platforms.html`, `/informatsionnaya-sistema.html`, `/catalog-matching.html`) в сыром HTML нет вообще — оно появляется только после JS. Поле `relatedSlugs` (заполнено у 24 из 24 статей репозитория, по 3–7 слагов) ведёт **только внутрь раздела**: ни один слаг не указывает на продуктовую страницу. Итог: 27 страниц с суммарно 23 тысячами слов замкнуты сами на себя, а после гидратации теряют и последнюю продуктовую ссылку (находка №5) | 27 / 27 | Пререндер вставляет только `#kb-prerender`, шапка/подвал живут в React-приложении: `scripts/prerender-knowledge-base.mjs:198` (`.replace('<div id="root"></div>', ...)`). Ограничение `relatedSlugs` — в данных: `src/data/knowledgeBase.ts:58` (тип `string[]`, интерпретируется как слаг базы знаний в `KnowledgeBaseArticle.tsx:189-192` и `prerender…mjs:410-412`) | Отдавать в пререндере статическую копию главного меню и подвала; расширить связанные материалы на продуктовые страницы (отдельным полем со ссылками, либо ставить 1–2 контекстные ссылки прямо в текст `context`/`conclusion`) | Сырой HTML каждой из 27 страниц содержит ≥ 15 уникальных внутренних ссылок, среди них ≥ 3 на продуктовые страницы; после гидратации ≥ 2 ссылки на продуктовые страницы находятся **внутри** `<article>`, а не только в шапке |
| 11 | **Неразрывных пробелов 0 на всех 27 страницах.** Проверено на сырых HTML: `&nbsp;` — 0 вхождений, символ U+00A0 — 0. При этом кандидатов (однобуквенный предлог + пробел перед словом) — **809** на раздел, от 17 до 50 на страницу. Ровно та же картина, что на восьми продуктовых страницах | 27 / 27 | Все тексты приходят из `src/data/knowledgeBase.ts` как обычные строки и проходят через `escape()` (`scripts/prerender-knowledge-base.mjs:122-130`) без типографской обработки. Единственное место, где `&nbsp;` проставлены руками, — статический подвал индекса раздела (`prerender…mjs:262-264`, 3 вхождения) | Прогнать тексты `knowledgeBase.ts` через типограф (предлоги, союзы, тире, числа с единицами) один раз при сборке или один раз по данным | В сыром HTML каждой из 27 страниц не менее 10 вхождений U+00A0/`&nbsp;`; число «висящих» однобуквенных предлогов на конце строки — 0 |
| 12 | **`meta keywords` пуст у 7 из 27 статей.** Пустые: `01-google-sheets-150k`, `09-custom-development-prototype`, `10-no-release-changes`, `11-ai-interface-data-safety`, `12-ai-prototype-rewrite`, `20-semantic-memory-without-vector-db`, `21-catalog-matching`. Само по себе поле поисковиками почти не используется, но здесь оно единственный машиночитаемый список ключей статьи — по нему же удобно проверять находку №6 | 7 / 27 | `metaKeywords` необязателен (`src/data/knowledgeBase.ts:47`), заполнен у 18 из 24 статей репозитория; пререндер при пустом значении просто вырезает тег (`prerender…mjs:194-198`) | Заполнить поле у семи статей | `metaKeywords` непуст у всех 27 |

---

## Расхождение репозитория и прода — отдельный риск

Замер делался по проду, а правки будут вноситься в `/root/backlogram`. Между
ними расхождение, и оно уже видно в цифрах:

- В `src/data/knowledgeBase.ts` — **24** статьи (`slug:` встречается 24 раза,
  последняя `21-catalog-matching`). На проде и в `sitemap.xml` — **27**:
  добавились `22-information-system-constructor`,
  `23-security-fault-tolerance`, `24-pure-business-design`.
- Расходятся и заголовки уже существующих статей. Пример:
  `01-google-sheets-150k` — в репозитории пререндер дал бы
  `<title>` длиной 71 символ («150 000 записей без ручного хаоса: когда
  Интеграм удобнее Google Sheets»), а прод отдаёт 47 символов
  («150 000 записей вместо Google Sheets — Интеграм»). Значит, на проде
  у статьи проставлен `seoTitle`, которого в репозитории нет.
- Расходится и группировка индекса раздела: в репозитории
  `scripts/prerender-knowledge-base.mjs:65-118` шесть групп, покрывающих
  22 слага; прод отдаёт **восемь** групп, включая новую «Основы:
  информационные системы (1)».
- Локальный репозиторий стоит на ветке `seo/kb-interlinking-breadcrumbs-cta`
  (HEAD `12021ea`), а не на `main`.

**По шаблону новые три статьи от старых не отличаются** — проверено на
`24-pure-business-design`: тот же единственный `<h1>`, совпадающий с сырым
HTML; своя `og:image`; тот же граф `TechArticle` + `BreadcrumbList` без
`datePublished`; те же 3 JSON-LD-блока после гидратации; тот же набор H2;
504 слова в сыром HTML против 1 339 после JS (62 % скрыто); нет CTA после
гидратации; переполнения шапки на 768px нет. То есть все 12 находок выше
на них распространяются в полной мере.

**Риск:** пока репозиторий не подтянут до состояния прода, любая правка
в `knowledgeBase.ts` статьи 22, 23 и 24 не заденет — а при пересборке из
текущего репозитория они **исчезнут с сайта** вместе с 3 записями в
`sitemap.xml` и с изменившейся группировкой индекса. Перед любыми
правками раздела первым шагом надо синхронизировать репозиторий с прод-
версией данных, иначе фикс на 27 страниц окажется фиксом на 24 с
регрессом на трёх.

Побочно на индексе раздела: группа-заглушка **«Остальные материалы (2)»**
собирает статьи, не попавшие ни в одну тематическую группу — сейчас там
`18-on-premise-procurement` и `20-semantic-memory-without-vector-db`
(`scripts/prerender-knowledge-base.mjs:146-155`). Для читателя и для
краулера это группа без темы; статьи надо разложить по смысловым группам
или завести им свою.

---

## Что уже в порядке

Это не список «всё плохо» — часть вещей, сломанных в продуктовом разделе,
в базе знаний сделана правильно, и трогать их не нужно.

- **H1 — чисто.** На всех 27 страницах ровно один `<h1>`, и его текст в
  сыром HTML **дословно совпадает** с текстом после гидратации (27/27).
  Ни исчезновения H1 (как было на `tokens.html`), ни подмены (как на
  `konstruktor-prilozhenij.html`) здесь нет. Заголовки уникальны на всех 27.
- **`og:image` у каждой статьи своя.** Проверено на всех 27: адрес всегда
  `https://ideav.ru/og/<slug>.png`, общей картинки раздела
  `/og/knowledge-base.png` не осталось нигде. Задача №7 из плана 12.08
  для базы знаний закрыта. Указаны `og:image:width/height`, есть
  `twitter:card=summary_large_image`, `twitter:image`.
- **Фикс шапки от 18.08 до раздела дошёл.** На 768px `header.scrollWidth`
  равен `header.clientWidth` — переполнение 0 px (было 1079 против 768 на
  продуктовых страницах). Горизонтального переполнения документа тоже нет
  ни на 1440px, ни на 768px.
- **Безымянных кнопок нет.** `namelessButtons: 0` на всех проверенных
  страницах; бывшая безымянная `button.text-slate-500` теперь имеет текст
  «Ещё». Задача №4 из плана 12.08 закрыта и здесь.
- **Каноникал самоссылочный на всех 27** и совпадает с URL в `sitemap.xml`
  и с внутренними ссылками — задача issue #341 держится, дублей
  `.html` / без-суффикса нет.
- **Метаданные не битые:** 27 уникальных `<title>` из 27, все в сыром HTML
  укладываются в 60 символов; описания 120–164 символа, длиннее 160 — одно.
  (Проблема появляется только после гидратации — см. находку №4.)
- **`BreadcrumbList` корректен по составу:** три позиции, `position` 1-2-3,
  абсолютные `item`, третья позиция — сама статья. Претензия только к
  дублированию (находка №2) и к отсутствию видимых крошек (находка №9).
- **`sitemap.xml` полон:** все 27 статей на месте, включая три новые.
- **`robots.txt` открыт для LLM-краулеров** — GPTBot, ClaudeBot,
  Google-Extended, PerplexityBot, CCBot и прочие разрешены явно; для
  раздела, который целиком рассчитан на цитирование в ответах моделей,
  это важнее среднего.
- **`<html lang="ru">`** проставлен и в сыром HTML, и после гидратации.
- **JS-ошибок нет:** `consoleErrors` пуст на всех проверенных страницах,
  на обеих ширинах.
- **Перелинковка внутри раздела живая:** `relatedSlugs` заполнен у всех 24
  статей репозитория (3–7 связей), плюс навигация «Предыдущая/Следующая»,
  плюс обратная ссылка на индекс. Битых внутренних ссылок не найдено.
  Внешние ссылки (`sourceUrl` на `github.com/ideav/crm`, ссылки на issue,
  TAdviser) отдают 200 — 404-ов нет.
- **Изображение снабжено `alt`, `width` и `height`** — CLS от обложки не
  будет. Претензия только к содержанию `alt` и к отсутствию других
  картинок (находка №8).

---

## Порядок работ

1. **Находка №1** — вернуть в пререндер недостающие 61 % текста. Самая
   дорогая: 14 373 слова контента на 27 страницах сейчас не участвуют в
   индексации гарантированно.
2. **Находки №2 и №3** — привести JSON-LD к одному блоку и проставить
   реальные даты. Делаются одной правкой в двух файлах.
3. **Находка №4** — один общий модуль вычисления `title`/`description`.
4. **Находка №5** — вернуть CTA живому посетителю (конверсия, не SEO).
5. **Находки №10 и №9** — шапка/подвал в сыром HTML, видимые крошки,
   ссылки в продуктовый кластер.
6. **Находки №6, №7, №8** — содержательные заголовки, `FAQPage`/`HowTo`,
   иллюстрации. Требуют работы с контентом, не только с кодом.
7. **Находки №11, №12** — типографика и `metaKeywords`, косметика.

Перед пунктом 1 — синхронизировать репозиторий с прод-версией данных
(см. раздел про расхождение), иначе правки не заденут три новые статьи.

---

## Сырые данные зондов

Пять статей, разных по типу: базовое сравнение с таблицей (`01`), длинная
инструкция с `flowDiagram` и `sources` (`08a`), короткая функциональная
(`14b`), про ИИ-агента (`19`) и новая, которой нет в репозитории (`24`).

### `01-google-sheets-150k.html`

```json
{
  "url": "https://ideav.ru/knowledge-base/01-google-sheets-150k.html",
  "http": 200,
  "raw": {
    "bytes": 14431,
    "words": 256,
    "h1": [
      "150 000 записей без ручного хаоса: когда Интеграм удобнее Google Sheets"
    ],
    "h2count": 3,
    "hasForm": false,
    "hasFileInput": false,
    "hasTextarea": false,
    "ogImage": "https://ideav.ru/og/01-google-sheets-150k.png",
    "title": "150 000 записей вместо Google Sheets — Интеграм",
    "jsBundles": [
      "index-Dx4b-LKo.js",
      "react-vendor-D57BBaBp.js",
      "motion-CWae_IBN.js"
    ],
    "articleDates": [
      {
        "type": "TechArticle",
        "datePublished": null,
        "dateModified": "2026-08-18"
      }
    ],
    "linksToAgentPlatforms": 0,
    "missingNbsp": 17,
    "phrases": {}
  },
  "rendered": {
    "w1440": {
      "h1": [
        "150 000 записей без ручного хаоса: когда Интеграм удобнее Google Sheets"
      ],
      "h2count": 6,
      "words": 564,
      "hasForm": false,
      "hasFileInput": false,
      "hasTextarea": false,
      "headerScrollWidth": 1440,
      "headerClientWidth": 1440,
      "docScrollWidth": 1440,
      "docClientWidth": 1440,
      "slateButton": {
        "text": "Ещё",
        "aria": null,
        "title": null
      },
      "namelessButtons": 0,
      "namelessButtonsSample": [],
      "navLinks": [
        " → /",
        "Технология → /#technology",
        "Как работаем → /#process",
        "Примеры → /#cases",
        "Цены → /#pricing",
        "Больше CRM → /sravnenie-s-bitrix-amocrm.html",
        "База знаний → /knowledge-base.html",
        "Блог → https://ideav.ru/blog/",
        "Информационная система → /informatsionnaya-sistema.html",
        "Платформы с ИИ-агентами → /agent-platforms.html",
        "Решения вместо Excel → /resheniya.html",
        "Конструктор вместо Excel → /konstruktor-prilozhenij.html",
        "Excel → приложение → /excel-to-app.html",
        "Сопоставление каталогов → /catalog-matching.html",
        "Предпосылки no-code конструктора → https://ideav.ru/blog/posts/predposylki-no-code-konstruktora-integram/",
        "Начать → https://ideav.ru/start.html",
        "Следующая Уйти от лимита строк Excel → /knowledge-base/02-excel-row-limit.html"
      ],
      "linksToAgentPlatforms": 1,
      "consoleErrors": [],
      "bodyTextLen": 4199
    },
    "w768": {
      "headerScrollWidth": 768,
      "headerClientWidth": 768,
      "docScrollWidth": 768,
      "docClientWidth": 768,
      "overflowPx": 0,
      "h1": [
        "150 000 записей без ручного хаоса: когда Интеграм удобнее Google Sheets"
      ]
    },
    "phrases": {},
    "h1RawVsRendered": "СОВПАДАЕТ"
  }
}
```

### `08a-vibe-coding-templates.html`

```json
{
  "url": "https://ideav.ru/knowledge-base/08a-vibe-coding-templates.html",
  "http": 200,
  "raw": {
    "bytes": 18083,
    "words": 558,
    "h1": [
      "Вайб-кодинг рабочих мест для Интеграма: как сгенерировать шаблон ИИ и вставить его в main.html"
    ],
    "h2count": 4,
    "hasForm": false,
    "hasFileInput": false,
    "hasTextarea": false,
    "ogImage": "https://ideav.ru/og/08a-vibe-coding-templates.png",
    "title": "Вайб-кодинг шаблонов для main.html — Интеграм",
    "jsBundles": [
      "index-Dx4b-LKo.js",
      "react-vendor-D57BBaBp.js",
      "motion-CWae_IBN.js"
    ],
    "articleDates": [
      {
        "type": "TechArticle",
        "datePublished": null,
        "dateModified": "2026-08-18"
      }
    ],
    "linksToAgentPlatforms": 0,
    "missingNbsp": 49,
    "phrases": {}
  },
  "rendered": {
    "w1440": {
      "h1": [
        "Вайб-кодинг рабочих мест для Интеграма: как сгенерировать шаблон ИИ и вставить его в main.html"
      ],
      "h2count": 9,
      "words": 1703,
      "hasForm": false,
      "hasFileInput": false,
      "hasTextarea": false,
      "headerScrollWidth": 1440,
      "headerClientWidth": 1440,
      "docScrollWidth": 1440,
      "docClientWidth": 1440,
      "slateButton": {
        "text": "Ещё",
        "aria": null,
        "title": null
      },
      "namelessButtons": 0,
      "namelessButtonsSample": [],
      "navLinks": [
        " → /",
        "Технология → /#technology",
        "Как работаем → /#process",
        "Примеры → /#cases",
        "Цены → /#pricing",
        "Больше CRM → /sravnenie-s-bitrix-amocrm.html",
        "База знаний → /knowledge-base.html",
        "Блог → https://ideav.ru/blog/",
        "Информационная система → /informatsionnaya-sistema.html",
        "Платформы с ИИ-агентами → /agent-platforms.html",
        "Решения вместо Excel → /resheniya.html",
        "Конструктор вместо Excel → /konstruktor-prilozhenij.html",
        "Excel → приложение → /excel-to-app.html",
        "Сопоставление каталогов → /catalog-matching.html",
        "Предпосылки no-code конструктора → https://ideav.ru/blog/posts/predposylki-no-code-konstruktora-integram/",
        "Начать → https://ideav.ru/start.html",
        "ПредыдущаяHTML-шаблоны вместо конструктора → /knowledge-base/08-html-templates.html",
        "Следующая Прототип быстрее заказной разработки → /knowledge-base/09-custom-development-prototype.html"
      ],
      "linksToAgentPlatforms": 1,
      "consoleErrors": [],
      "bodyTextLen": 12014
    },
    "w768": {
      "headerScrollWidth": 768,
      "headerClientWidth": 768,
      "docScrollWidth": 768,
      "docClientWidth": 768,
      "overflowPx": 0,
      "h1": [
        "Вайб-кодинг рабочих мест для Интеграма: как сгенерировать шаблон ИИ и вставить его в main.html"
      ]
    },
    "phrases": {},
    "h1RawVsRendered": "СОВПАДАЕТ"
  }
}
```

### `14b-dashboards.html`

```json
{
  "url": "https://ideav.ru/knowledge-base/14b-dashboards.html",
  "http": 200,
  "raw": {
    "bytes": 13782,
    "words": 259,
    "h1": [
      "Дашборды на тех же данных: чем Интеграм удобнее связки таблицы и внешнего BI"
    ],
    "h2count": 3,
    "hasForm": false,
    "hasFileInput": false,
    "hasTextarea": false,
    "ogImage": "https://ideav.ru/og/14b-dashboards.png",
    "title": "Дашборды на тех же данных без отдельного BI-кэша — Интеграм",
    "jsBundles": [
      "index-Dx4b-LKo.js",
      "react-vendor-D57BBaBp.js",
      "motion-CWae_IBN.js"
    ],
    "articleDates": [
      {
        "type": "TechArticle",
        "datePublished": null,
        "dateModified": "2026-08-18"
      }
    ],
    "linksToAgentPlatforms": 0,
    "missingNbsp": 24,
    "phrases": {}
  },
  "rendered": {
    "w1440": {
      "h1": [
        "Дашборды на тех же данных: чем Интеграм удобнее связки таблицы и внешнего BI"
      ],
      "h2count": 6,
      "words": 755,
      "hasForm": false,
      "hasFileInput": false,
      "hasTextarea": false,
      "headerScrollWidth": 1440,
      "headerClientWidth": 1440,
      "docScrollWidth": 1440,
      "docClientWidth": 1440,
      "slateButton": {
        "text": "Ещё",
        "aria": null,
        "title": null
      },
      "namelessButtons": 0,
      "namelessButtonsSample": [],
      "navLinks": [
        " → /",
        "Технология → /#technology",
        "Как работаем → /#process",
        "Примеры → /#cases",
        "Цены → /#pricing",
        "Больше CRM → /sravnenie-s-bitrix-amocrm.html",
        "База знаний → /knowledge-base.html",
        "Блог → https://ideav.ru/blog/",
        "Информационная система → /informatsionnaya-sistema.html",
        "Платформы с ИИ-агентами → /agent-platforms.html",
        "Решения вместо Excel → /resheniya.html",
        "Конструктор вместо Excel → /konstruktor-prilozhenij.html",
        "Excel → приложение → /excel-to-app.html",
        "Сопоставление каталогов → /catalog-matching.html",
        "Предпосылки no-code конструктора → https://ideav.ru/blog/posts/predposylki-no-code-konstruktora-integram/",
        "Начать → https://ideav.ru/start.html",
        "ПредыдущаяОтчёты на той же базе → /knowledge-base/14a-reports.html",
        "Следующая Локальное развёртывание и контроль → /knowledge-base/15-local-control-files.html"
      ],
      "linksToAgentPlatforms": 1,
      "consoleErrors": [],
      "bodyTextLen": 5652
    },
    "w768": {
      "headerScrollWidth": 768,
      "headerClientWidth": 768,
      "docScrollWidth": 768,
      "docClientWidth": 768,
      "overflowPx": 0,
      "h1": [
        "Дашборды на тех же данных: чем Интеграм удобнее связки таблицы и внешнего BI"
      ]
    },
    "phrases": {},
    "h1RawVsRendered": "СОВПАДАЕТ"
  }
}
```

### `19-ai-agent-app-build.html`

```json
{
  "url": "https://ideav.ru/knowledge-base/19-ai-agent-app-build.html",
  "http": 200,
  "raw": {
    "bytes": 17821,
    "words": 467,
    "h1": [
      "Приложение собирает ИИ-агент: чем подход Интеграма отличается от программистов и готовых коробок"
    ],
    "h2count": 4,
    "hasForm": false,
    "hasFileInput": false,
    "hasTextarea": false,
    "ogImage": "https://ideav.ru/og/19-ai-agent-app-build.png",
    "title": "Приложение собирает ИИ-агент — Интеграм",
    "jsBundles": [
      "index-Dx4b-LKo.js",
      "react-vendor-D57BBaBp.js",
      "motion-CWae_IBN.js"
    ],
    "articleDates": [
      {
        "type": "TechArticle",
        "datePublished": null,
        "dateModified": "2026-08-18"
      }
    ],
    "linksToAgentPlatforms": 0,
    "missingNbsp": 42,
    "phrases": {}
  },
  "rendered": {
    "w1440": {
      "h1": [
        "Приложение собирает ИИ-агент: чем подход Интеграма отличается от программистов и готовых коробок"
      ],
      "h2count": 8,
      "words": 972,
      "hasForm": false,
      "hasFileInput": false,
      "hasTextarea": false,
      "headerScrollWidth": 1440,
      "headerClientWidth": 1440,
      "docScrollWidth": 1440,
      "docClientWidth": 1440,
      "slateButton": {
        "text": "Ещё",
        "aria": null,
        "title": null
      },
      "namelessButtons": 0,
      "namelessButtonsSample": [],
      "navLinks": [
        " → /",
        "Технология → /#technology",
        "Как работаем → /#process",
        "Примеры → /#cases",
        "Цены → /#pricing",
        "Больше CRM → /sravnenie-s-bitrix-amocrm.html",
        "База знаний → /knowledge-base.html",
        "Блог → https://ideav.ru/blog/",
        "Информационная система → /informatsionnaya-sistema.html",
        "Платформы с ИИ-агентами → /agent-platforms.html",
        "Решения вместо Excel → /resheniya.html",
        "Конструктор вместо Excel → /konstruktor-prilozhenij.html",
        "Excel → приложение → /excel-to-app.html",
        "Сопоставление каталогов → /catalog-matching.html",
        "Предпосылки no-code конструктора → https://ideav.ru/blog/posts/predposylki-no-code-konstruktora-integram/",
        "Начать → https://ideav.ru/start.html",
        "ПредыдущаяOn-premise в реестре Минцифры → /knowledge-base/18-on-premise-procurement.html",
        "Следующая Память по смыслу без векторной БД → /knowledge-base/20-semantic-memory-without-vector-db.html"
      ],
      "linksToAgentPlatforms": 1,
      "consoleErrors": [],
      "bodyTextLen": 7105
    },
    "w768": {
      "headerScrollWidth": 768,
      "headerClientWidth": 768,
      "docScrollWidth": 768,
      "docClientWidth": 768,
      "overflowPx": 0,
      "h1": [
        "Приложение собирает ИИ-агент: чем подход Интеграма отличается от программистов и готовых коробок"
      ]
    },
    "phrases": {},
    "h1RawVsRendered": "СОВПАДАЕТ"
  }
}
```

### `24-pure-business-design.html`

```json
{
  "url": "https://ideav.ru/knowledge-base/24-pure-business-design.html",
  "http": 200,
  "raw": {
    "bytes": 18254,
    "words": 504,
    "h1": [
      "Pure Business Design: приложение по описанию задачи, без блоков и кубиков"
    ],
    "h2count": 4,
    "hasForm": false,
    "hasFileInput": false,
    "hasTextarea": false,
    "ogImage": "https://ideav.ru/og/24-pure-business-design.png",
    "title": "Pure Business Design — приложение по описанию задачи",
    "jsBundles": [
      "index-Dx4b-LKo.js",
      "react-vendor-D57BBaBp.js",
      "motion-CWae_IBN.js"
    ],
    "articleDates": [
      {
        "type": "TechArticle",
        "datePublished": null,
        "dateModified": "2026-08-18"
      }
    ],
    "linksToAgentPlatforms": 0,
    "missingNbsp": 50,
    "phrases": {}
  },
  "rendered": {
    "w1440": {
      "h1": [
        "Pure Business Design: приложение по описанию задачи, без блоков и кубиков"
      ],
      "h2count": 8,
      "words": 1339,
      "hasForm": false,
      "hasFileInput": false,
      "hasTextarea": false,
      "headerScrollWidth": 1440,
      "headerClientWidth": 1440,
      "docScrollWidth": 1440,
      "docClientWidth": 1440,
      "slateButton": {
        "text": "Ещё",
        "aria": null,
        "title": null
      },
      "namelessButtons": 0,
      "namelessButtonsSample": [],
      "navLinks": [
        " → /",
        "Технология → /#technology",
        "Как работаем → /#process",
        "Примеры → /#cases",
        "Цены → /#pricing",
        "Больше CRM → /sravnenie-s-bitrix-amocrm.html",
        "База знаний → /knowledge-base.html",
        "Блог → https://ideav.ru/blog/",
        "Информационная система → /informatsionnaya-sistema.html",
        "Платформы с ИИ-агентами → /agent-platforms.html",
        "Решения вместо Excel → /resheniya.html",
        "Конструктор вместо Excel → /konstruktor-prilozhenij.html",
        "Excel → приложение → /excel-to-app.html",
        "Сопоставление каталогов → /catalog-matching.html",
        "Предпосылки no-code конструктора → https://ideav.ru/blog/posts/predposylki-no-code-konstruktora-integram/",
        "Начать → https://ideav.ru/start.html",
        "ПредыдущаяБезопасность и отказоустойчивость → /knowledge-base/23-security-fault-tolerance.html"
      ],
      "linksToAgentPlatforms": 1,
      "consoleErrors": [],
      "bodyTextLen": 9855
    },
    "w768": {
      "headerScrollWidth": 768,
      "headerClientWidth": 768,
      "docScrollWidth": 768,
      "docClientWidth": 768,
      "overflowPx": 0,
      "h1": [
        "Pure Business Design: приложение по описанию задачи, без блоков и кубиков"
      ]
    },
    "phrases": {},
    "h1RawVsRendered": "СОВПАДАЕТ"
  }
}
```

### Сплошной прогон по всем 27 (сырой HTML против рендера)

Колонки: `слов в сыром | слов после JS | % скрыто | title совпадает |
description совпадает | H1 совпадает | H2 в сыром | H2 после JS |
блоков JSON-LD | CTA на excel-to-app после гидратации`

```
slug|rawW|spaW|%скрыто|titleSame|descSame|h1Same|rawH2|spaH2|ldBlocks|ctaExcel
01-google-sheets-150k.html|256|564|55%|false|false|true|3|6|3|false
02-excel-row-limit.html|310|670|54%|false|false|true|3|7|3|false
03-excel-file-versions.html|289|744|61%|false|false|true|3|6|3|false
04-related-tables.html|273|732|63%|false|false|true|3|6|3|false
05-access-rights.html|294|807|64%|false|false|true|3|6|3|false
06-airtable-control.html|441|997|56%|false|false|true|3|7|3|false
07-notion-relational-data.html|382|877|56%|false|false|true|4|8|3|false
08a-vibe-coding-templates.html|558|1703|67%|true|false|true|4|9|3|false
08-html-templates.html|323|863|63%|false|false|true|3|6|3|false
09-custom-development-prototype.html|357|726|51%|true|false|true|4|7|3|false
10-no-release-changes.html|232|591|61%|true|true|true|3|6|3|false
11-ai-interface-data-safety.html|301|640|53%|false|true|true|3|6|3|false
12-ai-prototype-rewrite.html|296|729|59%|true|false|true|3|6|3|false
13-api-json-export.html|244|754|68%|true|true|true|3|7|3|false
14a-reports.html|280|770|64%|true|false|true|3|6|3|false
14b-dashboards.html|259|755|66%|true|false|true|3|6|3|false
14-forms.html|303|765|60%|false|false|true|3|6|3|false
15-local-control-files.html|303|737|59%|false|true|true|3|6|3|false
16-pricing-policy.html|384|1160|67%|false|false|true|3|8|3|false
17-smart-google-import.html|332|1181|72%|true|false|true|3|8|3|false
18-on-premise-procurement.html|310|924|66%|true|false|true|3|7|3|false
19-ai-agent-app-build.html|467|972|52%|true|false|true|4|8|3|false
20-semantic-memory-without-vector-db.html|284|768|63%|false|false|true|3|7|3|false
21-catalog-matching.html|369|852|57%|false|false|true|4|8|3|false
22-information-system-constructor.html|379|854|56%|false|false|true|4|8|3|false
23-security-fault-tolerance.html|322|951|66%|false|false|true|3|6|3|false
24-pure-business-design.html|504|1339|62%|true|false|true|4|8|3|false

ИТОГ: titleSame 11/27 | descSame 4/27 | h1Same 27/27 | ldBlocks==3 27/27 | ctaExcel 0/27
слов в сыром HTML суммарно 9052 | после JS 23425 | скрыто 14373 (61%)
```

Полные выгрузки рядом с этим файлом: `sweep27.json` (сырой HTML по 27
URL), `sweep27-rendered.json` (сырой против рендера по 27 URL),
`probe2-out.json` (JSON-LD, ссылки, картинки по пяти статьям).
Зонды: `probe.mjs` (исходный), `probe2.mjs`, `probe3.mjs`.
