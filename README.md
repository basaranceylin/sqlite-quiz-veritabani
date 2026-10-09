# SQLite ile Quiz Veri Tabanı

Quiz sisteminin veri katmanı: kullanıcılar, oturumlar, sorular, cevaplar ve oturum takibi.

## Teslim edilen dosyalar

| Dosya | Açıklama |
|---|---|
| `schema.sql` | Tablolar, kısıtlar, indeksler ve tetikleyiciler |
| `seed.py` | Örnek kullanıcı, oturum, soru ve cevap verisini üretir |
| `queries.sql` | Canlı takip, oturum sonuçları ve puan sıralaması sorguları |
| `quiz.db` | Hazır, çalışan veri tabanı (`seed.py` çıktısı) |
| `run_queries.py` | `queries.sql` içindeki sorguları çalıştırıp yazdırır |
| `integrity_test.py` | Veri bütünlüğü denemeleri |
| `app.py` | Tkinter arayüzü (ek) |

## Kurulum ve çalıştırma

Gereken: Python 3 (SQLite ve Tkinter Python ile birlikte gelir, ek kurulum yok). Tüm dosyalar aynı klasörde olmalıdır.

1. Veri tabanını sıfırdan kurmak ve örnek veriyi yüklemek için:
   ```
   python seed.py
   ```
   Bu komut varsa eski `quiz.db` dosyasını siler, `schema.sql` ile tabloları oluşturur ve verileri ekler. Sonunda tablolardaki kayıt sayılarını yazdırır.
2. Sorguları çalıştırmak için:
   ```
   python run_queries.py
   ```
3. Veri bütünlüğü denemeleri için:
   ```
   python integrity_test.py
   ```
4. Arayüz için (isteğe bağlı):
   ```
   python app.py
   ```

Her bağlantıda `PRAGMA foreign_keys = ON;` çalıştırılır (SQLite'ta bu ayar kalıcı değildir).

## Veri modeli

```
kullanicilar            oturumlar               sorular
------------            ---------               -------
id (PK)                 id (PK)                 id (PK)
kullanici_adi (UNIQUE)  baslik                  metin (UNIQUE)
kayit_zamani            durum                   secenek_a..secenek_d
                        baslangic_zamani        dogru_cevap (A/B/C/D)
                        bitis_zamani
     |                       |                       |
     |                       +-----------+-----------+
     |                                   |
     |                           oturum_sorulari
     |                           ---------------
     |                           oturum_id (FK) --+
     |                           soru_id   (FK) --+-- PK (oturum_id, soru_id)
     |                           sira  (oturum_id ile UNIQUE)
     |                                   |
     |                                   | (oturum_id, soru_id) bileşik FK
     |                                   |
     +---------------------------- cevaplar
                                   --------
                                   id (PK)
                                   kullanici_id (FK)
                                   oturum_id, soru_id (bileşik FK)
                                   verilen_cevap (A/B/C/D veya NULL)
                                   cevap_zamani
                                   UNIQUE (kullanici_id, oturum_id, soru_id)
```

İlişkiler:

- Bir oturumda birçok soru, bir soru birçok oturumda yer alabilir (çoktan çoğa). Bu ilişki `oturum_sorulari` tablosuyla kurulur.
- Bir kullanıcı birçok cevap verebilir. Her cevap bir kullanıcıya, bir oturuma ve bir soruya bağlıdır.

### Kısıtlar ve neden varlar

| Kısıt | Amaç |
|---|---|
| `oturum_sorulari` PRIMARY KEY (oturum_id, soru_id) | Aynı soru aynı oturuma iki kez eklenemez |
| `oturum_sorulari` UNIQUE (oturum_id, sira) | Bir oturumda aynı sırada iki soru olmaz |
| `cevaplar` UNIQUE (kullanici_id, oturum_id, soru_id) | **Cevaplama kuralı:** bir kullanıcı bir oturumdaki bir soruya yalnızca bir kez cevap verir |
| `cevaplar` bileşik FOREIGN KEY (oturum_id, soru_id) → `oturum_sorulari` | Cevap, sorunun gerçekten yer aldığı oturuma ait olmak zorundadır |
| `oturumlar.durum` CHECK | Yalnızca `beklemede`, `devam_ediyor`, `bitti` |
| `oturumlar` zaman CHECK'leri | Bitiş başlangıçtan sonra olmalı; bitiş zamanı **yalnızca** `bitti` oturumda dolu olur (`(durum = 'bitti') = (bitis_zamani IS NOT NULL)`); `beklemede` dışındaki oturumun başlangıç zamanı dolu olmalı |
| `sorular.dogru_cevap`, `cevaplar.verilen_cevap` CHECK | Yalnızca A, B, C, D (cevapta NULL = boş) |
| İndeksler | `cevaplar(oturum_id, soru_id)`, `cevaplar(kullanici_id)`, `oturum_sorulari(soru_id)` ile sorgular hızlanır |

### Tetikleyiciler (trigger)

| Tetikleyici | Amaç |
|---|---|
| `trg_cevap_oturum_aktif` (cevaplar, BEFORE INSERT) | Cevap yalnızca durumu `devam_ediyor` olan oturuma eklenebilir; başlamamış ve bitmiş oturuma cevap reddedilir |
| `trg_cevap_guncelleme_oturum_aktif` (cevaplar, BEFORE UPDATE) | Var olan bir cevap yalnızca durumu `devam_ediyor` olan oturumda değiştirilebilir; bitmiş oturumun sonuçları sonradan değiştirilemez. Cevabın başka oturuma taşınması da reddedilir |
| `trg_oturum_durum_gecisi` (oturumlar, BEFORE UPDATE OF durum) | Durum yalnızca `beklemede → devam_ediyor → bitti` sırasıyla değişebilir; geri dönüş ve atlama reddedilir |

## Oturum durumları

- **beklemede:** başlangıç zamanı planlıdır (boş da olabilir), bitiş zamanı boştur, cevap yoktur.
- **devam_ediyor:** başlamıştır, bitiş zamanı boştur, cevaplar gelmektedir.
- **bitti:** başlangıç ve bitiş zamanı doludur, yeni cevap kabul edilmez.

Örnek veride oturumlar:

| Oturum | Konu | Durum | Başlangıç |
|---|---|---|---|
| 1 | Toplama Quizi | bitti | 2026-10-01 14:00 |
| 2 | Çarpma Quizi | devam_ediyor | 2026-10-06 10:00 |
| 3 | Çıkarma Quizi | beklemede | 2026-10-12 14:00 |
| 4 | Bölme Quizi | beklemede | 2026-10-14 14:00 |
| 5 | Başkentler Quizi | beklemede | 2026-10-16 14:00 |

## Puanlama kuralı

| Cevap durumu | Puan |
|---|---|
| Doğru cevap (`verilen_cevap = dogru_cevap`) | 1 |
| Yanlış cevap (seçilmiş ama doğru değil) | 0 |
| Boş cevap (`verilen_cevap IS NULL`) | 0 |

Boş cevap `NULL` olarak saklanır; yani kullanıcı soruyu bilerek boş bırakmıştır ve kaydı vardır. Bir oturumda **hiç kaydı olmayan** soru ise henüz cevaplanmamış demektir; sonuç sorgusu yalnızca kaydı olan satırları saydığı için bu sorular `bos` sütununa girmez (bitmiş oturumda herkes tüm soruları işaretlediği için fark oluşmaz). SQL'de `NULL = 'A'` ne doğru ne yanlış sonuç verir, bu yüzden yanlış cevaplar sorguda ayrıca `verilen_cevap IS NOT NULL AND verilen_cevap <> dogru_cevap` ile sayılır. Puan = doğru cevap sayısıdır. Eşit puanlı kullanıcılar `RANK()` ile aynı sırayı alır.

## Sorgular (`queries.sql`)

1. **Canlı takip:** her oturumun durumu, soru sayısı, katılımcı sayısı, cevap sayısı, ilerleme yüzdesi (katılımcılara göre) ve `tum_kullanici_yuzde` (kayıtlı tüm kullanıcılara göre). Sorgu her çalıştırıldığında güncel veriyi okur.
2. **Oturum sonuçları:** 1 numaralı oturum için kullanıcı başına doğru, yanlış, boş, puan ve sıra.
3. **En yüksek puanlılar:** tüm oturumlardaki toplam puana göre ilk 10 kullanıcı. Eşit puanlılar kullanıcı adına göre alfabetik sıralanır ve liste 10. satırda kesilir; bu yüzden 10. sıradaki puanla eşit olan bazı kullanıcılar listeye girmeyebilir.

### Katılımcı ve ilerleme tanımı

- **Katılımcı:** ilgili oturumda en az bir cevap kaydı olan kullanıcıdır (boş bırakılan cevap da kayıttır). Hiç cevap vermemiş kullanıcı katılımcı sayılmaz.
- **İlerleme yüzdesi:** `cevap sayısı / (katılımcı sayısı × soru sayısı) × 100`. Oran katılımcılara göre hesaplanır. **Tüm kullanıcılara göre ilerleme** (`tum_kullanici_yuzde`) ise `cevap sayısı / (kullanıcı sayısı × soru sayısı) × 100` olup oturum 2 için %52,6'dır.
- Örnek veride oturum 1'de 50 katılımcı ve 1000 cevap vardır (%100). Oturum 2'de 47 katılımcı ve 526 cevap vardır (%56; tüm kullanıcılara göre %52,6). 3 kullanıcı henüz hiç cevap vermemiştir. Oturum 3, 4 ve 5'te cevap olmadığı için katılımcı 0 ve ilerleme %0'dır.

## Kayıt sayılarını doğrulayan sorgular

```sql
SELECT COUNT(*) AS kullanici_sayisi FROM kullanicilar;          -- 50
SELECT COUNT(*) AS oturum_sayisi FROM oturumlar;                -- 5
SELECT COUNT(*) AS soru_sayisi FROM sorular;                    -- 100
SELECT COUNT(DISTINCT soru_id) AS oturumlara_bagli_soru
FROM oturum_sorulari;                                           -- 100
SELECT oturum_id, COUNT(*) AS soru_sayisi
FROM oturum_sorulari GROUP BY oturum_id;                        -- her oturumda 20
SELECT COUNT(*) AS cevap_sayisi FROM cevaplar;                  -- 1526
```

## Veri bütünlüğü denemeleri (`integrity_test.py`)

Hatalı kayıtlar denenir ve her denemeden sonra `rollback()` yapılır (veri değişmez). Toplam 20 denemenin 3'ü geçerli işlemdir ve kabul edilir, 17'si reddedilir:

| Deneme | Sonuç |
|---|---|
| Geçerli cevap (devam eden oturum) | Kabul |
| Olmayan kullanıcıya ait cevap | Reddedilir (FOREIGN KEY) |
| Olmayan soruya cevap | Reddedilir (FOREIGN KEY) |
| Oturumda bulunmayan soruya cevap | Reddedilir (bileşik FOREIGN KEY) |
| Aynı soruya ikinci cevap | Reddedilir (UNIQUE) |
| Geçersiz şık ('E') | Reddedilir (CHECK) |
| Başlamamış oturuma cevap | Reddedilir (trigger) |
| Bitmiş oturuma cevap | Reddedilir (trigger) |
| Aynı soruyu aynı oturuma tekrar ekleme | Reddedilir (UNIQUE) |
| Geçersiz oturum durumu | Reddedilir (CHECK) |
| Bitişi başlangıçtan önce olan oturum | Reddedilir (CHECK) |
| Aynı kullanıcı adı | Reddedilir (UNIQUE) |
| Bitmiş oturumu geri açma (bitti → devam_ediyor) | Reddedilir (trigger) |
| Başlamamış oturumu atlayarak bitirme (beklemede → bitti) | Reddedilir (trigger) |
| Beklemede oturuma bitiş zamanı yazma | Reddedilir (CHECK) |
| Devam eden oturumun başlangıç zamanı boş | Reddedilir (CHECK) |
| Biten oturumun bitiş zamanı boş | Reddedilir (CHECK) |
| Bitmiş oturumdaki cevabı değiştirme | Reddedilir (trigger) |
| Devam eden oturumdaki cevabı değiştirme | Kabul |
| Geçerli geçiş (beklemede → devam_ediyor) | Kabul |

## Veri üretimi (`seed.py`)

- Kullanıcılar `kullanici_01 ... kullanici_50` adıyla üretilir.
- 100 soru betikle üretilir: toplama, çıkarma, çarpma, bölme (matematik) ve başkentler, her biri 20 soru. Her kategori bir oturuma bağlıdır (yukarıdaki oturum tablosu).
- Biten oturum gerçek akışla oluşturulur: önce `devam_ediyor` olarak açılır, cevaplar eklenir, sonunda `bitti` yapılıp bitiş zamanı yazılır.
- Bitmiş oturumda her kullanıcı tüm soruları cevaplar; devam eden oturumda her kullanıcı rastgele sayıda (0-20) soru cevaplar, bu yüzden kısmi ilerleme vardır. Cevapların yaklaşık %5'i boş, %65'i doğru, kalanı yanlıştır.
- `random.seed(42)` kullanıldığı için her çalıştırmada aynı veri üretilir.

## Arayüz (`app.py`, ek)

Python ile gelen Tkinter kullanılır, ek kurulum gerekmez. Çalıştırmak için:

```
python app.py
```

Üç sekmesi vardır (mor-pembe pastel tema, emojili):

- **Canlı Takip:** kullanıcı, oturum, soru ve cevap sayılarını gösteren özet kartları (sayılar sayarak artar), her oturum için durum etiketi, katılımcı/cevap sayısı ve yumuşakça dolan ilerleme çubuğu içeren kart. Devam eden oturum için büyük ilerleme çubuğu ve motive edici mesaj vardır. Sorgu her 3 saniyede bir yeniden çalışır, güncel veriyi gösterir. Üst başlıkta saat ve yanıp sönen "canlı oturum var" göstergesi bulunur. **"Canlı simülasyonu başlat"** düğmesi, devam eden oturumdaki katılımcılar için her adımda (yaklaşık 0,6 saniyede bir) 5 rastgele cevabı veri tabanına yazar; yazılan cevaplar "Son cevaplar" panelinde akar. Tüm katılımcılar bütün soruları cevaplayınca simülasyon kendiliğinden durur.
- **Quiz Çöz:** kullanıcı ve oturum seçilir, sorular sırayla gelir. Şıklar tıklanabilir kartlardır; cevap verince doğru şık yeşil, yanlış seçilen şık kırmızı olur ve kısa bir beklemeden sonra sonraki soruya geçilir. Doğru sayısı ve üst üste doğru serisi gösterilir. Klavye kısayolları: A-D şık seçer, Enter cevaplar, Boşluk boş bırakır. Oturum bitince puana göre bir mesaj çıkar. Kısıtlara aykırı bir kayıt (ör. başlamamış oturuma cevap) veri tabanı tarafından reddedilir ve hata penceresinde gösterilir.
- **Sonuçlar:** seçilen oturumun ilk 3 kişisi için podyum kartları, katılımcı sayısı, ortalama ve en yüksek puan özeti, oturum sonuç tablosu (sıra, doğru, yanlış, boş, puan) ve tüm oturumlardaki en yüksek puanlı 10 kullanıcı. İlk üç sıra madalya emojisiyle işaretlenir.

Not: Arayüzden verilen cevaplar ve simülasyon `quiz.db` dosyasına yazılır, yani veriyi değiştirir. Veriyi ilk haline (1526 cevap) döndürmek için `python seed.py` çalıştırılır.

## Bilinen sınırlamalar

- Cevap silme (DELETE) denetlenmez; bitmiş bir oturumun cevabı silinebilir. Ekleme ve güncelleme ise trigger'larla korunur.
- Yeni bir oturum kaydı ilk eklenirken herhangi bir durumda oluşturulabilir; durum geçiş kuralı yalnızca sonraki güncellemelere uygulanır.
- Cevap zamanı (`cevap_zamani`) oturumun başlangıç-bitiş aralığında mı diye denetlenmez; seed verisi bu aralığa uyar.
- Katılımlar ayrı bir tabloda tutulmaz; katılımcı, en az bir cevabı olan kullanıcı olarak tanımlanır. Bu yüzden henüz hiç cevap vermemiş bir kullanıcı oturum takibinde görünmez.