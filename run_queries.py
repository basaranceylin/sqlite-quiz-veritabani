import sqlite3

con = sqlite3.connect("quiz.db")
con.execute("PRAGMA foreign_keys = ON")

sorgular = open("queries.sql", encoding="utf-8").read().split(";")
for sorgu in sorgular:
    if not sorgu.strip():
        continue
    print("=" * 70)
    print(sorgu.strip().splitlines()[0])  # ilk satir = baslik
    cur = con.execute(sorgu)
    print([d[0] for d in cur.description])
    for satir in cur.fetchall()[:12]:      # ekran dolmasin diye ilk 12 satir
        print(satir)
con.close()