#!/usr/bin/env python3
"""Сборка ядра clinch.by из результатов скрапера Wordstat. Регион 149 (Беларусь).

Отличия от того, чем собрано исходное ядро — по разбору 19.08.2026:
  * затравки идут ОТ КАТЕГОРИЙ КАТАЛОГА, а не от тем блога;
  * голова кластера сохраняется наравне с хвостом;
  * рядом с числом лежат регион и дата съёма;
  * дедуп по нормализованной фразе, а не по точной строке;
  * видно, из какой затравки пришла фраза и упёрся ли кластер в потолок 200.

Разметка намерения черновая: она для сортировки, решение принимает человек.
"""
import json, os, re, sys, urllib.parse, urllib.request
from collections import defaultdict
from datetime import date

API  = "http://127.0.0.1:8081"
KEY  = os.popen("grep '^API_KEY=' /root/incoming/wordstat-scraper/.env | cut -d= -f2").read().strip()
BASE = "/root/seo/clinch"
REGION = "149"
CAP  = 200          # потолок скрапера: MAX_PAGES=10 × 20 строк
TODAY = date.today().isoformat()

def get(phrase):
    u = f"{API}/results/" + urllib.parse.quote(phrase) + f"?region={REGION}&result_type=table"
    r = urllib.request.Request(u, headers={"x-api-key": KEY})
    return json.loads(urllib.request.urlopen(r, timeout=60).read().decode()).get("data", [])

INTENT = [
    ("покупка",   r"(купить|заказать|цена|цены|стоимость|сколько стоит|прайс|интернет.?магазин|доставка|опт)"),
    ("выбор",     r"(как выбрать|какие|какой|лучш|рейтинг|топ |сравнени|отзыв|обзор|размер|унци)"),
    ("гео",       r"(минск|беларус|белорус|гомел|витебск|брест|могилев|гродно)"),
    ("бренд",     r"(clinch|клинч|everlast|эверласт|adidas|адидас|green hill|грин хилл|venum|fairtex|rdx|title|hayabusa|ultimatum|reyes)"),
    ("учебное",   r"(что такое|как сделать|своими руками|техника|тренировк|упражнен|видео|история|правила)"),
    ("нецелевое", r"(порно|бу |б/у|авито|скачать|игра|мем|смайл|фото|обои|рисунок|тату)"),
]
def intent(p):
    low = p.lower()
    for name, rx in INTENT:
        if re.search(rx, low):
            return name
    return "общий"

def norm(p):
    return re.sub(r"\s+", " ", p.strip().lower()).replace("ё", "е")

def main():
    seeds = json.load(open(f"{BASE}/zatravki.json", encoding="utf-8"))
    best, seen_seeds, capped, missing = {}, defaultdict(set), [], []
    per_seed = {}
    for cat, phrases in seeds.items():
        for seed in phrases:
            try:
                rows = get(seed)
            except Exception as e:
                missing.append((seed, str(e)[:60])); continue
            if not rows:
                missing.append((seed, "пусто")); continue
            per_seed[seed] = (len(rows), sum(r["count"] for r in rows))
            if len(rows) >= CAP:
                capped.append(seed)
            for r in rows:
                ph, cnt = r["phrase"].strip(), r["count"]
                k = norm(ph)
                seen_seeds[k].add(seed)
                if k not in best or cnt > best[k][0]:
                    best[k] = (cnt, ph, cat, seed)

    out = f"{BASE}/yadro-clinch-{TODAY}.csv"
    with open(out, "w", encoding="utf-8", newline="") as f:
        f.write("Категория;Ключевое слово;Частота Yandex;Регион;Дата съёма;Затравка;Затравок;Намерение;Слов\n")
        for k, (cnt, ph, cat, seed) in sorted(best.items(), key=lambda x: -x[1][0]):
            f.write(f"{cat};{ph};{cnt};{REGION};{TODAY};{seed};{len(seen_seeds[k])};{intent(ph)};{len(ph.split())}\n")

    print(f"собрано уникальных фраз: {len(best)}")
    print(f"суммарная частота: {sum(v[0] for v in best.values()):,}")
    print(f"затравок отработано: {len(per_seed)} из {sum(len(v) for v in seeds.values())}")
    if capped:
        print(f"упёрлись в потолок {CAP} строк ({len(capped)}): {', '.join(capped)}")
    if missing:
        print(f"не отдали результат ({len(missing)}): {missing}")
    print(f"файл: {out}")

if __name__ == "__main__":
    main()
