-- 1) CANLI TAKIP: her oturumun anlik durumu ve cevaplanma ilerlemesi
WITH ozet AS (
    SELECT o.id, o.baslik, o.durum, o.baslangic_zamani, o.bitis_zamani,
           (SELECT COUNT(*) FROM oturum_sorulari os
             WHERE os.oturum_id = o.id) AS soru_sayisi,
           (SELECT COUNT(DISTINCT c.kullanici_id) FROM cevaplar c
             WHERE c.oturum_id = o.id) AS katilimci_sayisi,
           (SELECT COUNT(*) FROM cevaplar c
             WHERE c.oturum_id = o.id) AS cevap_sayisi
    FROM oturumlar o
)
SELECT *,
       CASE WHEN katilimci_sayisi * soru_sayisi = 0 THEN 0
            ELSE ROUND(100.0 * cevap_sayisi / (katilimci_sayisi * soru_sayisi), 1)
       END AS ilerleme_yuzde,
       ROUND(100.0 * cevap_sayisi /
             ((SELECT COUNT(*) FROM kullanicilar) * soru_sayisi), 1) AS tum_kullanici_yuzde
FROM ozet
ORDER BY id;

-- 2) OTURUM SONUCLARI: 1 numarali oturum, puana gore siralama
SELECT RANK() OVER (ORDER BY SUM(CASE WHEN c.verilen_cevap = s.dogru_cevap THEN 1 ELSE 0 END) DESC) AS sira,
       k.kullanici_adi,
       SUM(CASE WHEN c.verilen_cevap = s.dogru_cevap THEN 1 ELSE 0 END) AS dogru,
       SUM(CASE WHEN c.verilen_cevap IS NOT NULL AND c.verilen_cevap <> s.dogru_cevap THEN 1 ELSE 0 END) AS yanlis,
       SUM(CASE WHEN c.verilen_cevap IS NULL THEN 1 ELSE 0 END) AS bos,
       SUM(CASE WHEN c.verilen_cevap = s.dogru_cevap THEN 1 ELSE 0 END) AS puan
FROM cevaplar c
JOIN kullanicilar k ON k.id = c.kullanici_id
JOIN sorular s ON s.id = c.soru_id
WHERE c.oturum_id = 1
GROUP BY k.id
ORDER BY sira, k.kullanici_adi;

-- 3) EN YUKSEK PUANLI 10 KULLANICI (tum oturumlar toplami)
SELECT k.kullanici_adi,
       COUNT(DISTINCT c.oturum_id) AS oturum_sayisi,
       SUM(CASE WHEN c.verilen_cevap = s.dogru_cevap THEN 1 ELSE 0 END) AS toplam_puan
FROM cevaplar c
JOIN kullanicilar k ON k.id = c.kullanici_id
JOIN sorular s ON s.id = c.soru_id
GROUP BY k.id
ORDER BY toplam_puan DESC, k.kullanici_adi
LIMIT 10;