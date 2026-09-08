#!/usr/bin/env python3
"""Сверка: старое ядро SMI против пересобранного, обе — против каталога."""
import csv, glob, re, collections, sys

def norm(p): return re.sub(r"\s+"," ",p.strip().lower()).replace("ё","е")

old={}
for r in csv.DictReader(open('/root/seo/clinch/_____all_keywords.csv',encoding='utf-8-sig'),delimiter=';'):
    k=norm(r['Ключевое слово'])
    try: c=int(r['Частота Yandex'])
    except: c=0
    old[k]=max(old.get(k,0),c)

f=sorted(glob.glob('/root/seo/clinch/yadro-clinch-*.csv'))[-1]
new={}; cat={}; intent={}
for r in csv.DictReader(open(f,encoding='utf-8'),delimiter=';'):
    k=norm(r['Ключевое слово']); c=int(r['Частота Yandex'])
    if c>=new.get(k,-1): new[k]=c; cat[k]=r['Категория']; intent[k]=r['Намерение']

print(f"старое ядро: {len(old):,} фраз, {sum(old.values()):,} показов")
print(f"новое ядро:  {len(new):,} фраз, {sum(new.values()):,} показов   ({f.split('/')[-1]})")
print(f"общих фраз: {len(set(old)&set(new)):,} | только в новом: {len(set(new)-set(old)):,} | потеряно из старого: {len(set(old)-set(new)):,}")
lost=sorted(((old[k],k) for k in set(old)-set(new)), reverse=True)[:10]
print("  самое частотное из старого, чего нет в новом:", [(v,k) for v,k in lost[:6]])

print("\nПО КАТЕГОРИЯМ (новое ядро):")
tovary={"Боксерские перчатки":52,"Шлемы":30,"Бинты для бокса":25,"Капы":14,"Боксерская форма":10,
        "Обувь для бокса":7,"Футболки":7,"Лапы":6,"Снарядные перчатки":4,"Защитное снаряжение":3,
        "Скакалки":2,"Мешки и груши":1,"Бренд и общее":0}
agg=collections.defaultdict(lambda:[0,0])
for k,v in new.items():
    a=agg[cat[k]]; a[0]+=1; a[1]+=v
print(f"  {'категория':<24}{'товаров':>8}{'фраз':>7}{'показов':>10}{'было в старом':>15}")
oldcat={"Боксерские перчатки":715,"Шлемы":30,"Бинты для бокса":9,"Капы":0,"Боксерская форма":24,
        "Обувь для бокса":9,"Футболки":0,"Лапы":2,"Снарядные перчатки":35,"Защитное снаряжение":66,
        "Скакалки":0,"Мешки и груши":961,"Бренд и общее":4}
for c,(n,s) in sorted(agg.items(), key=lambda x:-x[1][1]):
    print(f"  {c:<24}{tovary.get(c,'?'):>8}{n:>7}{s:>10,}{oldcat.get(c,0):>15,}")

print("\nПО НАМЕРЕНИЮ:")
ia=collections.defaultdict(lambda:[0,0])
for k,v in new.items():
    a=ia[intent[k]]; a[0]+=1; a[1]+=v
tot=sum(new.values())
for i,(n,s) in sorted(ia.items(), key=lambda x:-x[1][1]):
    print(f"  {i:<12} фраз {n:>5}  показов {s:>8,}  ({s*100//tot}%)")

print("\nПО ЧИСЛУ СЛОВ:")
wc=collections.Counter(len(k.split()) for k in new)
print("  " + "  ".join(f"{n}сл:{wc[n]}" for n in sorted(wc)))

print("\nГОЛОВЫ КАТЕГОРИЙ — есть ли теперь:")
for h in ["боксерские перчатки","боксерский шлем","бинты для бокса","капа боксерская","форма для бокса",
          "боксерки","футболка для бокса","боксерские лапы","снарядные перчатки","скакалка",
          "боксерский мешок","боксерская груша","clinch"]:
    print(f"  {h:<24} новое: {new.get(h,'—'):>7}   старое: {old.get(h,'—'):>7}")
