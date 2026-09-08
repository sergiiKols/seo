cd /root/seo/ideav-ru/kb-2026-08-18/
KEY=$(grep '^API_KEY=' /root/incoming/wordstat-scraper/.env | cut -d= -f2)
for i in $(seq 1 120); do
 done_all=1
 for p in "резервное копирование" "безопасность персональных данных" "152 фз" "шифрование данных" "журнал доступа" "информационная безопасность" "отказоустойчивость системы" "резервное копирование данных"; do
  f=$(echo "$p" | tr ' ' '_')
  if [ -s "ws23-ok-$f.json" ]; then continue; fi
  e=$(python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$p")
  curl -sS "http://127.0.0.1:8081/results/$e?type=table" -H "x-api-key: $KEY" -o "ws23-$f.json"
  c=$(python3 -c "import json;print(json.load(open('ws23-$f.json'))['count'])" 2>/dev/null || echo 0)
  if [ "$c" -gt 0 ]; then cp "ws23-$f.json" "ws23-ok-$f.json"; echo "READY $p = $c"; else done_all=0; fi
 done
 [ $done_all -eq 1 ] && { echo ALLDONE; break; }
 sleep 20
done
