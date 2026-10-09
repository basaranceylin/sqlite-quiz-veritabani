import os
import random
import sqlite3
from datetime import datetime, timedelta

random.seed(42)  # her çalıştırmada aynı veri çıksın


def yaz(tarih):
    # tarihi veri tabanına yazılacak metne çevirir
    return tarih.strftime("%Y-%m-%d %H:%M:%S")


# --- Veri tabanını sıfırdan kur ---
if os.path.exists("quiz.db"):
    os.remove("quiz.db")
con = sqlite3.connect("quiz.db")
con.execute("PRAGMA foreign_keys = ON")
con.executescript(open("schema.sql", encoding="utf-8").read())


# --- Soru hazırlama ---
def soru_hazirla(metin, dogru, digerleri):
    # doğru cevabı diğer 3 şıkla karıştırır ve doğru şıkkın harfini bulur
    secenekler = [str(dogru)] + [str(d) for d in digerleri]
    random.shuffle(secenekler)
    harf = "ABCD"[secenekler.index(str(dogru))]
    return (metin, secenekler[0], secenekler[1], secenekler[2], secenekler[3], harf)


def sayili_soru(metin, dogru):
    # yanlış şıklar doğru cevaba yakın sayılar
    return soru_hazirla(metin, dogru, [dogru - 1, dogru + 1, dogru + 2])


toplama = []
cikarma = []
carpma = []
bolme = []
for i in range(20):
    a = 10 + i * 3
    b = 50 - i
    toplama.append(sayili_soru(f"Toplama: {a} + {b} = ?", a + b))

    a = 50 + i * 2
    b = 10 + i
    cikarma.append(sayili_soru(f"Çıkarma: {a} - {b} = ?", a - b))

    a = i + 5
    b = (i % 9) + 3
    carpma.append(sayili_soru(f"Çarpma: {a} x {b} = ?", a * b))

    bolen = (i % 9) + 2
    sonuc = i + 2
    bolme.append(sayili_soru(f"Bölme: {bolen * sonuc} / {bolen} = ?", sonuc))

baskentler = [
    ("Türkiye", "Ankara"), ("Fransa", "Paris"), ("Almanya", "Berlin"),
    ("İtalya", "Roma"), ("İspanya", "Madrid"), ("Japonya", "Tokyo"),
    ("Mısır", "Kahire"), ("Yunanistan", "Atina"), ("Rusya", "Moskova"),
    ("Çin", "Pekin"), ("Kanada", "Ottawa"), ("Brezilya", "Brasilia"),
    ("Avustralya", "Kanberra"), ("Hindistan", "Yeni Delhi"),
    ("Portekiz", "Lizbon"), ("Polonya", "Varşova"), ("Norveç", "Oslo"),
    ("İsveç", "Stockholm"), ("Arjantin", "Buenos Aires"),
    ("Güney Kore", "Seul"),
]
baskent_sorulari = []
for ulke, baskent in baskentler:
    digerleri = [b for u, b in baskentler if b != baskent]
    yanlislar = random.sample(digerleri, 3)
    baskent_sorulari.append(
        soru_hazirla(f"{ulke} ülkesinin başkenti neresidir?", baskent, yanlislar))

# --- Kullanıcılar ---
for i in range(1, 51):
    kayit = datetime(2026, 9, 20) + timedelta(hours=i)
    con.execute(
        "INSERT INTO kullanicilar (kullanici_adi, kayit_zamani) VALUES (?, ?)",
        (f"kullanici_{i:02d}", yaz(kayit)))

# --- Oturumlar ---
# 1. oturum önce 'devam_ediyor' açılır, cevaplar eklenir, en sonda 'bitti' yapılır
# (cevap sadece devam eden oturuma eklenebildiği için)
oturumlar = [
    ("Toplama Quizi", "devam_ediyor", datetime(2026, 10, 1, 14, 0), toplama),
    ("Çarpma Quizi", "devam_ediyor", datetime(2026, 10, 6, 10, 0), carpma),
    ("Çıkarma Quizi", "beklemede", datetime(2026, 10, 12, 14, 0), cikarma),
    ("Bölme Quizi", "beklemede", datetime(2026, 10, 14, 14, 0), bolme),
    ("Başkentler Quizi", "beklemede", datetime(2026, 10, 16, 14, 0), baskent_sorulari),
]

oturum_sorulari = {}   # oturum_id -> [(soru_id, doğru_harf), ...]
baslangiclar = {}      # oturum_id -> başlangıç zamanı
for baslik, durum, baslangic, sorular in oturumlar:
    cur = con.execute(
        "INSERT INTO oturumlar (baslik, durum, baslangic_zamani) VALUES (?, ?, ?)",
        (baslik, durum, yaz(baslangic)))
    oturum_id = cur.lastrowid
    baslangiclar[oturum_id] = baslangic
    liste = []
    for sira, soru in enumerate(sorular, start=1):
        cur = con.execute(
            "INSERT INTO sorular (metin, secenek_a, secenek_b, secenek_c, "
            "secenek_d, dogru_cevap) VALUES (?, ?, ?, ?, ?, ?)", soru)
        soru_id = cur.lastrowid
        con.execute(
            "INSERT INTO oturum_sorulari (oturum_id, soru_id, sira) VALUES (?, ?, ?)",
            (oturum_id, soru_id, sira))
        liste.append((soru_id, soru[5]))
    oturum_sorulari[oturum_id] = liste


# --- Cevaplar ---
def cevap_sec(dogru):
    r = random.random()
    if r < 0.05:
        return None          # boş bıraktı
    if r < 0.70:
        return dogru         # doğru cevap
    yanlislar = [h for h in "ABCD" if h != dogru]
    return random.choice(yanlislar)


for oturum_id in (1, 2):
    for kullanici_id in range(1, 51):
        if oturum_id == 1:
            kac_soru = 20                    # herkes hepsini cevapladı
        else:
            kac_soru = random.randint(0, 20)  # devam ediyor, herkes farklı yerde
        for soru_id, dogru in oturum_sorulari[oturum_id][:kac_soru]:
            zaman = baslangiclar[oturum_id] + timedelta(minutes=random.randint(1, 55))
            con.execute(
                "INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, "
                "verilen_cevap, cevap_zamani) VALUES (?, ?, ?, ?, ?)",
                (kullanici_id, oturum_id, soru_id, cevap_sec(dogru), yaz(zaman)))

# --- 1. oturumu bitir ---
bitis = baslangiclar[1] + timedelta(hours=1)
con.execute("UPDATE oturumlar SET durum = 'bitti', bitis_zamani = ? WHERE id = 1",
            (yaz(bitis),))

con.commit()

# --- Kayıt sayılarını yazdır ---
for tablo in ["kullanicilar", "oturumlar", "sorular", "oturum_sorulari", "cevaplar"]:
    sayi = con.execute(f"SELECT COUNT(*) FROM {tablo}").fetchone()[0]
    print(f"{tablo}: {sayi}")
con.close()