#!/usr/bin/env python3
"""Сборка нового семантического ядра из результатов скрапера Wordstat.

Читает затравки из yadro-zatravki.json (сгруппированы по направлениям),
забирает по каждой кластер из API скрапера и складывает в CSV того же
формата, что старое ядро: Направление;Ключевое слово;Частота Yandex;
Частота Google;Подпапка — чтобы существующие инструменты не переписывать.

Дополнительно пишет колонку «Затравка» — из какого запроса пришла фраза,
и помечает тип намерения простыми маркерами. Разметка намерения здесь
грубая и служит только для сортировки: окончательное решение принимает
человек или агент, это правило мастерской.
"""
import json, os, re, sys, urllib.parse, urllib.request
from collections import defaultdict

API = "http://127.0.0.1:8081"
KEY = os.popen("grep '^API_KEY=' /root/incoming/wordstat-scraper/.env | cut -d= -f2").read().strip()
BASE = "/root/seo/ideav-ru/kb-2026-08-18"

def get(phrase):
    u = f"{API}/results/" + urllib.parse.quote(phrase) + "?type=table"
    r = urllib.request.Request(u, headers={"x-api-key": KEY})
    return json.loads(urllib.request.urlopen(r, timeout=60).read().decode()).get("data", [])

# Маркеры намерения. Порядок важен: первое совпадение выигрывает.
INTENT = [
    ("учебное",     r"\b(что такое|это|простыми словами|для чайников|пошагов|инструкц|пример|урок|курс|обучени|учебник|реферат|тест|экзамен|егэ|вуз|специальност|professia|professiya|кем работать|зарплат)"),
    ("покупка",     r"\b(купить|заказать|цена|цены|стоимость|сколько стоит|тариф|прайс|внедрени|подключить|demo|демо|консультац)"),
    ("выбор",       r"\b(аналог|альтернатив|замена|заменить|вместо|сравнени|или |лучш|топ |рейтинг|обзор|выбрать|выбор)"),
    ("проблема",    r"\b(не работает|ошибк|тормозит|лимит|ограничени|проблем|падает|виснет|потер)"),
    ("навигация",   r"\b(скачать|войти|вход|личный кабинет|официальный сайт|\.com|\.ru|бесплатно)"),
]
def intent(p):
    low = p.lower()
    for name, rx in INTENT:
        if re.search(rx, low): return name
    return "общий"

def main():
    seeds = json.load(open(f"{BASE}/yadro-zatravki.json"))
    best = {}          # фраза -> (частота, направление, затравка)
    per_seed = {}
    missing = []
    for napravlenie, phrases in seeds.items():
        for seed in phrases:
            try:
                rows = get(seed)
            except Exception as e:
                missing.append((seed, str(e)[:60])); continue
            if not rows:
                missing.append((seed, "пусто")); continue
            per_seed[seed] = (len(rows), sum(r["count"] for r in rows))
            for r in rows:
                ph, cnt = r["phrase"].strip(), r["count"]
                # фраза могла прийти из нескольких затравок — держим максимум
                if ph not in best or cnt > best[ph][0]:
                    best[ph] = (cnt, napravlenie, seed)

    out = f"{BASE}/yadro-peresobrannoe.csv"
    with open(out, "w", encoding="utf-8") as f:
        f.write("Направление;Ключевое слово;Частота Yandex;Частота Google;Подпапка;Затравка;Намерение\n")
        for ph, (cnt, nap, seed) in sorted(best.items(), key=lambda x: -x[1][0]):
            safe = ph.replace(";", ",")
            f.write(f"{nap};{safe};{cnt};0;;{seed};{intent(ph)}\n")

    # Сводка
    by_nap = defaultdict(lambda: [0, 0])
    by_int = defaultdict(lambda: [0, 0])
    for ph, (cnt, nap, seed) in best.items():
        by_nap[nap][0] += 1; by_nap[nap][1] += cnt
        i = intent(ph)
        by_int[i][0] += 1;  by_int[i][1] += cnt

    print(f"Собрано уникальных фраз: {len(best)}")
    print(f"Суммарная частота:       {sum(v[0] for v in best.values())}")
    print(f"Затравок отработало:     {len(per_seed)} из {sum(len(v) for v in seeds.values())}")
    if missing:
        print(f"Не собрано ({len(missing)}): " + ", ".join(m[0] for m in missing[:10]))
    print("\nПо направлениям:")
    for nap, (n, s) in sorted(by_nap.items(), key=lambda x: -x[1][1]):
        print(f"  {nap:34} фраз {n:>6}  сумма {s:>9}")
    print("\nПо намерению:")
    for i, (n, s) in sorted(by_int.items(), key=lambda x: -x[1][1]):
        print(f"  {i:12} фраз {n:>6}  сумма {s:>9}")
    print(f"\nФайл: {out}")

if __name__ == "__main__":
    main()
