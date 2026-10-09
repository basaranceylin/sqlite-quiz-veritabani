import sqlite3

con = sqlite3.connect("quiz.db")
con.execute("PRAGMA foreign_keys = ON")

CEVAP = ("INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap) "
         "VALUES (?, ?, ?, ?)")


def dene(aciklama, sql, params=()):
    print(f"\n> {aciklama}")
    try:
        con.execute(sql, params)
        print("  KABUL EDILDI")
    except sqlite3.IntegrityError as e:
        print(f"  REDDEDILDI: {e}")
    finally:
        con.rollback()  # veri tabani degismesin


# Yardimci veriler
bos = con.execute("""
    SELECT k.id, os.soru_id
    FROM kullanicilar k
    JOIN oturum_sorulari os ON os.oturum_id = 2
    LEFT JOIN cevaplar c ON c.kullanici_id = k.id
         AND c.oturum_id = os.oturum_id AND c.soru_id = os.soru_id
    WHERE c.id IS NULL
    LIMIT 1
""").fetchone()  # oturum 2'de henuz cevaplanmamis kullanici + soru
var = con.execute(
    "SELECT kullanici_id, soru_id FROM cevaplar WHERE oturum_id = 2 LIMIT 1"
).fetchone()  # oturum 2'de zaten cevabi olan kayit
s1 = con.execute(
    "SELECT soru_id FROM oturum_sorulari WHERE oturum_id = 1 LIMIT 1").fetchone()[0]
s3 = con.execute(
    "SELECT soru_id FROM oturum_sorulari WHERE oturum_id = 3 LIMIT 1").fetchone()[0]

print("=== CEVAPLAR ===")
dene("Gecerli cevap, devam eden oturum (beklenen: kabul)", CEVAP, (bos[0], 2, bos[1], "A"))
dene("Olmayan kullanici (id=9999)", CEVAP, (9999, 2, bos[1], "A"))
dene("Olmayan soru (id=9999)", CEVAP, (1, 2, 9999, "A"))
dene("Soru var ama oturum 2'de yok (soru 1 oturum 1'e ait)", CEVAP, (1, 2, 1, "A"))
dene("Ayni kullanici ayni soruya ikinci kez cevap", CEVAP, (var[0], 2, var[1], "B"))
dene("Gecersiz sik ('E')", CEVAP, (bos[0], 2, bos[1], "E"))
dene("Baslamamis oturuma (3) cevap", CEVAP, (1, 3, s3, "A"))
dene("Bitmis oturuma (1) cevap", CEVAP, (1, 1, s1, "A"))

print("\n=== OTURUM-SORU, OTURUM, KULLANICI ===")
dene("Soru 1 oturum 1'e tekrar ekleniyor",
     "INSERT INTO oturum_sorulari (oturum_id, soru_id, sira) VALUES (1, 1, 99)")
dene("Gecersiz oturum durumu",
     "INSERT INTO oturumlar (baslik, durum) VALUES ('Deneme', 'bozuk')")
dene("Bitis zamani baslangictan once",
     "INSERT INTO oturumlar (baslik, durum, baslangic_zamani, bitis_zamani) "
     "VALUES ('Deneme', 'bitti', '2026-10-01 15:00:00', '2026-10-01 14:00:00')")
dene("Ayni kullanici adi tekrar",
     "INSERT INTO kullanicilar (kullanici_adi) VALUES ('kullanici_01')")

print("\n=== ZAMAN / DURUM TUTARLILIGI ===")
dene("Beklemede oturuma bitis zamani yazma",
     "INSERT INTO oturumlar (baslik, durum, baslangic_zamani, bitis_zamani) "
     "VALUES ('Deneme', 'beklemede', '2026-10-20 10:00:00', '2026-10-20 11:00:00')")
dene("Devam eden oturumun baslangic zamani bos",
     "INSERT INTO oturumlar (baslik, durum) VALUES ('Deneme', 'devam_ediyor')")
dene("Biten oturumun bitis zamani bos",
     "INSERT INTO oturumlar (baslik, durum, baslangic_zamani) "
     "VALUES ('Deneme', 'bitti', '2026-10-20 10:00:00')")

print("\n=== CEVAP GUNCELLEME ===")
dene("Bitmis oturumdaki cevabi degistirme",
     "UPDATE cevaplar SET verilen_cevap = 'A' WHERE oturum_id = 1 AND id = "
     "(SELECT MIN(id) FROM cevaplar WHERE oturum_id = 1)")
dene("Devam eden oturumdaki cevabi degistirme (beklenen: kabul)",
     "UPDATE cevaplar SET verilen_cevap = 'A' WHERE oturum_id = 2 AND id = "
     "(SELECT MIN(id) FROM cevaplar WHERE oturum_id = 2)")

print("\n=== DURUM GECISLERI ===")
dene("Bitmis oturumu geri acma (bitti -> devam_ediyor)",
     "UPDATE oturumlar SET durum = 'devam_ediyor' WHERE id = 1")
dene("Beklemedeki oturumu atlayarak bitirme (beklemede -> bitti)",
     "UPDATE oturumlar SET durum = 'bitti', bitis_zamani = '2026-10-13 15:00:00' "
     "WHERE id = 3")
dene("Gecerli gecis (beklemede -> devam_ediyor, beklenen: kabul)",
     "UPDATE oturumlar SET durum = 'devam_ediyor' WHERE id = 3")

con.close()