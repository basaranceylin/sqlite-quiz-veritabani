PRAGMA foreign_keys = ON;

CREATE TABLE kullanicilar (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kullanici_adi TEXT NOT NULL UNIQUE,
    kayit_zamani  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE oturumlar (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    baslik            TEXT NOT NULL,
    durum             TEXT NOT NULL DEFAULT 'beklemede'
                      CHECK (durum IN ('beklemede', 'devam_ediyor', 'bitti')),
    baslangic_zamani  TEXT,
    bitis_zamani      TEXT,
    CHECK (bitis_zamani IS NULL OR baslangic_zamani IS NOT NULL),
    CHECK (bitis_zamani IS NULL OR bitis_zamani > baslangic_zamani),
    CHECK ((durum = 'bitti') = (bitis_zamani IS NOT NULL)),
    CHECK (durum = 'beklemede' OR baslangic_zamani IS NOT NULL)
);

CREATE TABLE sorular (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    metin        TEXT NOT NULL UNIQUE,
    secenek_a    TEXT NOT NULL,
    secenek_b    TEXT NOT NULL,
    secenek_c    TEXT NOT NULL,
    secenek_d    TEXT NOT NULL,
    dogru_cevap  TEXT NOT NULL CHECK (dogru_cevap IN ('A', 'B', 'C', 'D'))
);

CREATE TABLE oturum_sorulari (
    oturum_id  INTEGER NOT NULL REFERENCES oturumlar(id) ON DELETE CASCADE,
    soru_id    INTEGER NOT NULL REFERENCES sorular(id),
    sira       INTEGER NOT NULL CHECK (sira > 0),
    PRIMARY KEY (oturum_id, soru_id),
    UNIQUE (oturum_id, sira)
);

CREATE TABLE cevaplar (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kullanici_id  INTEGER NOT NULL REFERENCES kullanicilar(id),
    oturum_id     INTEGER NOT NULL,
    soru_id       INTEGER NOT NULL,
    verilen_cevap TEXT CHECK (verilen_cevap IN ('A', 'B', 'C', 'D')),
    cevap_zamani  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (kullanici_id, oturum_id, soru_id),
    FOREIGN KEY (oturum_id, soru_id)
        REFERENCES oturum_sorulari(oturum_id, soru_id)
);

CREATE INDEX idx_cevaplar_oturum ON cevaplar(oturum_id, soru_id);
CREATE INDEX idx_cevaplar_kullanici ON cevaplar(kullanici_id);
CREATE INDEX idx_oturum_sorulari_soru ON oturum_sorulari(soru_id);

CREATE TRIGGER trg_cevap_oturum_aktif
BEFORE INSERT ON cevaplar
WHEN (SELECT durum FROM oturumlar WHERE id = NEW.oturum_id) IS NOT 'devam_ediyor'
BEGIN
    SELECT RAISE(ABORT, 'Cevap yalnizca devam eden oturuma eklenebilir');
END;

CREATE TRIGGER trg_oturum_durum_gecisi
BEFORE UPDATE OF durum ON oturumlar
WHEN NOT (
    OLD.durum = NEW.durum
    OR (OLD.durum = 'beklemede'    AND NEW.durum = 'devam_ediyor')
    OR (OLD.durum = 'devam_ediyor' AND NEW.durum = 'bitti')
)
BEGIN
    SELECT RAISE(ABORT, 'Gecersiz durum gecisi');
END;

CREATE TRIGGER trg_cevap_guncelleme_oturum_aktif
BEFORE UPDATE ON cevaplar
WHEN (SELECT durum FROM oturumlar WHERE id = OLD.oturum_id) IS NOT 'devam_ediyor'
  OR NEW.oturum_id <> OLD.oturum_id
BEGIN
    SELECT RAISE(ABORT, 'Cevap yalnizca devam eden oturumda guncellenebilir');
END;
