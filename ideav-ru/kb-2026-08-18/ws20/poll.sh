#!/bin/bash
KEY=$(grep '^API_KEY=' /root/incoming/wordstat-scraper/.env | cut -d= -f2)
cd /root/seo/ideav-ru/kb-2026-08-18/ws20
PH=("поиск по смыслу" "векторный поиск" "эмбеддинги" "база знаний для ии" "llm с базой данных" "поиск информации в компании" "семантическая память" "как быстро найти нужный документ" "иерархические данные в базе данных" "рекурсивный запрос sql" "with recursive" "поиск похожих записей" "поиск дубликатов в базе данных" "нечеткий поиск")
for i in $(seq 1 60); do
  done_all=1
  for p in "${PH[@]}"; do
    f=$(echo "$p" | tr ' ' '_')
    [ -s "$f.done" ] && continue
    e=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$p")
    curl -sS "http://127.0.0.1:8081/results/$e?type=table" -H "x-api-key: $KEY" -o "$f.json"
    if python3 -c "import json,sys;d=json.load(open('$f.json'));sys.exit(0 if d.get('data') else 1)"; then
      touch "$f.done"
    else
      done_all=0
    fi
  done
  [ $done_all -eq 1 ] && break
  sleep 15
done
echo FINISHED
