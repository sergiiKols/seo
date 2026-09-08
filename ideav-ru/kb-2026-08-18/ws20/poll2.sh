#!/bin/bash
KEY=$(grep '^API_KEY=' /root/incoming/wordstat-scraper/.env | cut -d= -f2)
cd /root/seo/ideav-ru/kb-2026-08-18/ws20
PH=("поиск по смыслу" "векторный поиск" "эмбеддинги" "база знаний для ии" "llm с базой данных" "поиск информации в компании" "семантическая память" "как быстро найти нужный документ" "иерархические данные в базе данных" "поиск похожих записей" "поиск дубликатов в базе данных")
for i in $(seq 1 200); do
  all=1
  for p in "${PH[@]}"; do
    f=$(echo "$p" | tr ' ' '_')
    [ -f "$f.done" ] && continue
    e=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$p")
    curl -sS "http://127.0.0.1:8081/results/$e?type=table" -H "x-api-key: $KEY" -o "$f.json" 2>/dev/null
    if python3 -c "import json,sys;d=json.load(open('$f.json'));sys.exit(0 if d.get('data') else 1)" 2>/dev/null; then
      touch "$f.done"; echo "READY: $p"
    else all=0; fi
  done
  [ $all -eq 1 ] && break
  sleep 20
done
echo ALLDONE
