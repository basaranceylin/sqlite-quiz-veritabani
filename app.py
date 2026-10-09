import random
import sqlite3
import tkinter as tk
from collections import deque
from datetime import datetime
from tkinter import ttk, messagebox, font as tkfont

DB = "quiz.db"

# --- Renkler (pastel mor / pembe tema) ---
METIN = "#2d2a4a"
ARKA = "#f7f5ff"
KART = "#ffffff"
CIZGI = "#e4e0f7"
MOR = "#6c5ce7"
MOR_KOYU = "#5846d6"
MOR_ACIK = "#ece9ff"
PEMBE = "#ff7eb6"
MINT = "#2ec4b6"
YESIL = "#2fb980"
YESIL_KOYU = "#25946a"
YESIL_ACIK = "#dcf7ea"
KIRMIZI = "#ef5b6b"
KIRMIZI_ACIK = "#ffe1e5"
TURUNCU = "#ff9f5a"
TURUNCU_ACIK = "#fff0e0"
GRI = "#8b88a8"
GRI_KOYU = "#6f6c8c"
GRI_ACIK = "#efedf8"

DURUM_ADI = {
    "bitti": "✔ Bitti",
    "devam_ediyor": "● Devam ediyor",
    "beklemede": "○ Beklemede",
}
DURUM_RENK = {  # (yazı rengi, zemin rengi)
    "bitti": (YESIL, YESIL_ACIK),
    "devam_ediyor": (TURUNCU, TURUNCU_ACIK),
    "beklemede": (GRI, GRI_ACIK),
}
DURUM_EMOJI = {"bitti": "✅", "devam_ediyor": "🔥", "beklemede": "⏳"}
MADALYA = {1: "🥇", 2: "🥈", 3: "🥉"}

FONT = "TkDefaultFont"


def font_sec():
    """Sistemde var olan ilk güzel yazı tipini seçer (Windows, Mac, Linux)."""
    global FONT
    mevcut = set(tkfont.families())
    for ad in ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Ubuntu",
               "Noto Sans", "DejaVu Sans"):
        if ad in mevcut:
            FONT = ad
            return


def yazi(boyut=10, kalin=False):
    return (FONT, boyut, "bold") if kalin else (FONT, boyut)


def renk_karisim(r1, r2, t):
    """İki renk arasında t (0-1) oranında geçiş rengi üretir."""
    a = [int(r1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(r2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * t) for x, y in zip(a, b))


SAYILAR_SQL = """
SELECT (SELECT COUNT(*) FROM kullanicilar),
       (SELECT COUNT(*) FROM oturumlar),
       (SELECT COUNT(*) FROM sorular),
       (SELECT COUNT(*) FROM cevaplar)
"""

TAKIP_SQL = """
WITH ozet AS (
    SELECT o.id, o.baslik, o.durum,
           (SELECT COUNT(*) FROM oturum_sorulari os
             WHERE os.oturum_id = o.id) AS soru_sayisi,
           (SELECT COUNT(DISTINCT c.kullanici_id) FROM cevaplar c
             WHERE c.oturum_id = o.id) AS katilimci,
           (SELECT COUNT(*) FROM cevaplar c
             WHERE c.oturum_id = o.id) AS cevap
    FROM oturumlar o
)
SELECT baslik, durum, soru_sayisi, katilimci, cevap,
       CASE WHEN katilimci * soru_sayisi = 0 THEN 0
            ELSE ROUND(100.0 * cevap / (katilimci * soru_sayisi), 1)
       END
FROM ozet
ORDER BY id
"""

SONRAKI_SORU_SQL = """
SELECT s.id, os.sira, s.metin, s.secenek_a, s.secenek_b, s.secenek_c, s.secenek_d
FROM oturum_sorulari os
JOIN sorular s ON s.id = os.soru_id
WHERE os.oturum_id = ?
  AND NOT EXISTS (
      SELECT 1 FROM cevaplar c
      WHERE c.kullanici_id = ? AND c.oturum_id = os.oturum_id
        AND c.soru_id = os.soru_id)
ORDER BY os.sira
LIMIT 1
"""

SIM_SQL = """
SELECT k.id, os.oturum_id, os.soru_id, s.dogru_cevap
FROM oturum_sorulari os
JOIN oturumlar o ON o.id = os.oturum_id AND o.durum = 'devam_ediyor'
JOIN sorular s ON s.id = os.soru_id
CROSS JOIN kullanicilar k
WHERE EXISTS (SELECT 1 FROM cevaplar c
              WHERE c.kullanici_id = k.id AND c.oturum_id = os.oturum_id)
  AND NOT EXISTS (SELECT 1 FROM cevaplar c
                  WHERE c.kullanici_id = k.id AND c.oturum_id = os.oturum_id
                    AND c.soru_id = os.soru_id)
ORDER BY RANDOM()
LIMIT 5
"""

ILERLEME_SQL = """
SELECT (SELECT COUNT(*) FROM oturum_sorulari WHERE oturum_id = ?),
       (SELECT COUNT(*) FROM cevaplar WHERE oturum_id = ? AND kullanici_id = ?)
"""

KULLANICI_PUAN_SQL = """
SELECT COALESCE(SUM(CASE WHEN c.verilen_cevap = s.dogru_cevap THEN 1 ELSE 0 END), 0),
       COUNT(*)
FROM cevaplar c
JOIN sorular s ON s.id = c.soru_id
WHERE c.kullanici_id = ? AND c.oturum_id = ?
"""

SONUC_SQL = """
SELECT RANK() OVER (ORDER BY SUM(CASE WHEN c.verilen_cevap = s.dogru_cevap THEN 1 ELSE 0 END) DESC),
       k.kullanici_adi,
       SUM(CASE WHEN c.verilen_cevap = s.dogru_cevap THEN 1 ELSE 0 END),
       SUM(CASE WHEN c.verilen_cevap IS NOT NULL AND c.verilen_cevap <> s.dogru_cevap THEN 1 ELSE 0 END),
       SUM(CASE WHEN c.verilen_cevap IS NULL THEN 1 ELSE 0 END),
       SUM(CASE WHEN c.verilen_cevap = s.dogru_cevap THEN 1 ELSE 0 END)
FROM cevaplar c
JOIN kullanicilar k ON k.id = c.kullanici_id
JOIN sorular s ON s.id = c.soru_id
WHERE c.oturum_id = ?
GROUP BY k.id
ORDER BY 1, k.kullanici_adi
"""

TOP10_SQL = """
SELECT RANK() OVER (ORDER BY toplam_puan DESC), kullanici_adi, oturum_sayisi, toplam_puan
FROM (
    SELECT k.kullanici_adi,
           COUNT(DISTINCT c.oturum_id) AS oturum_sayisi,
           SUM(CASE WHEN c.verilen_cevap = s.dogru_cevap THEN 1 ELSE 0 END) AS toplam_puan
    FROM cevaplar c
    JOIN kullanicilar k ON k.id = c.kullanici_id
    JOIN sorular s ON s.id = c.soru_id
    GROUP BY k.id
)
ORDER BY toplam_puan DESC, kullanici_adi
LIMIT 10
"""


def sorgu(sql, params=()):
    """Her çağrıda veri tabanını yeniden açar, böylece hep güncel veriyi okur."""
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    try:
        return con.execute(sql, params).fetchall()
    finally:
        con.close()


def cevap_kaydet(kullanici_id, oturum_id, soru_id, cevap):
    con = sqlite3.connect(DB)
    con.execute("PRAGMA foreign_keys = ON")
    try:
        con.execute(
            "INSERT INTO cevaplar (kullanici_id, oturum_id, soru_id, verilen_cevap) "
            "VALUES (?, ?, ?, ?)", (kullanici_id, oturum_id, soru_id, cevap))
        con.commit()
    finally:
        con.close()



def tablo_olustur(ust, kolonlar, yukseklik):
    """kolonlar: (id, başlık, genişlik) listesi. Tabloyu ve kaydırma çubuğunu 'ust' içine koyar."""
    tablo = ttk.Treeview(ust, columns=[k[0] for k in kolonlar],
                         show="headings", height=yukseklik)
    kaydirma = ttk.Scrollbar(ust, orient="vertical", command=tablo.yview)
    tablo.configure(yscrollcommand=kaydirma.set)
    for kid, baslik, genislik in kolonlar:
        tablo.heading(kid, text=baslik)
        tablo.column(kid, width=genislik, anchor="center")
    tablo.pack(side="left", fill="both", expand=True)
    kaydirma.pack(side="right", fill="y")
    # satır renkleri (madalyalar + zebra çizgisi)
    tablo.tag_configure("tek", background="white")
    tablo.tag_configure("cift", background="#f8f6ff")
    tablo.tag_configure("altin", background="#fff1c2")
    tablo.tag_configure("gumus", background="#e9ecf4")
    tablo.tag_configure("bronz", background="#f8dfcb")
    return tablo


def tablo_doldur(tablo, satirlar):
    """İlk sütun sıra: ilk 3 sıraya madalya emojisi ve renk verir, diğerlerini zebra yapar."""
    renk = {1: "altin", 2: "gumus", 3: "bronz"}
    tablo.delete(*tablo.get_children())
    for i, satir in enumerate(satirlar):
        sira = satir[0]
        etiket = f"{MADALYA[sira]} {sira}" if sira in MADALYA else str(sira)
        tablo.insert("", "end", values=(etiket,) + tuple(satir[1:]),
                     tags=(renk.get(sira, "cift" if i % 2 else "tek"),))


def kart_cerceve(ust):
    """Beyaz, ince çerçeveli kart."""
    return tk.Frame(ust, bg=KART, highlightthickness=1, highlightbackground=CIZGI)


class YuvarlakCubuk(tk.Canvas):
    """Uçları yuvarlak, değişirken yumuşakça kayan ilerleme çubuğu (0-100)."""

    def __init__(self, ust, yukseklik=14, renk=MOR, zemin=GRI_ACIK, bg=KART):
        super().__init__(ust, height=yukseklik, bg=bg, highlightthickness=0)
        self.h = yukseklik
        self.renk = renk
        self.zemin = zemin
        self.hedef = 0.0
        self.simdiki = 0.0
        self._is = None
        self.bind("<Configure>", lambda e: self.ciz())

    def ciz(self):
        self.delete("all")
        w, h = self.winfo_width(), self.h
        if w < h * 2:
            return
        r = h / 2
        self.create_line(r, r, w - r, r, width=h, capstyle="round", fill=self.zemin)
        if self.simdiki > 0.3:
            x = r + (w - 2 * r) * self.simdiki / 100
            self.create_line(r, r, x, r, width=h, capstyle="round", fill=self.renk)

    def ayarla(self, deger, anim=True):
        self.hedef = max(0.0, min(100.0, float(deger)))
        if not anim:
            self.simdiki = self.hedef
            self.ciz()
        elif self._is is None:
            self._adim()

    def _adim(self):
        fark = self.hedef - self.simdiki
        if abs(fark) < 0.3:
            self.simdiki = self.hedef
            self.ciz()
            self._is = None
            return
        self.simdiki += fark * 0.2
        self.ciz()
        self._is = self.after(20, self._adim)


class SayiKarti(tk.Frame):
    """Renkli özet kartı: emoji + sayı (değişince sayarak artar) + ad."""

    def __init__(self, ust, emoji, ad, renk):
        super().__init__(ust, bg=renk)
        tk.Label(self, text=emoji, bg=renk, font=yazi(22)).pack(
            side="left", padx=(16, 8), pady=8)
        sag = tk.Frame(self, bg=renk)
        sag.pack(side="left", pady=6)
        self.deger = tk.Label(sag, text="0", bg=renk, fg="white", font=yazi(24, True))
        self.deger.pack(anchor="w")
        tk.Label(sag, text=ad, bg=renk, fg="white", font=yazi(10)).pack(anchor="w")
        self.simdiki = 0
        self.hedef = 0
        self._is = None

    def ayarla(self, hedef):
        self.hedef = hedef
        if self._is is None:
            self._adim()

    def _adim(self):
        fark = self.hedef - self.simdiki
        if fark == 0:
            self._is = None
            return
        adim = max(1, abs(fark) // 6)
        self.simdiki += adim if fark > 0 else -adim
        self.deger.config(text=str(self.simdiki))
        self._is = self.after(30, self._adim)


class OturumKarti(tk.Frame):
    """Canlı Takip'teki tek bir oturumun kartı."""

    def __init__(self, ust):
        super().__init__(ust, bg=KART, highlightthickness=1, highlightbackground=CIZGI)
        self.emoji = tk.Label(self, bg=KART, font=yazi(18))
        self.emoji.grid(row=0, column=0, rowspan=2, padx=(14, 8), pady=4)
        self.baslik = tk.Label(self, bg=KART, fg=METIN, font=yazi(11, True), anchor="w")
        self.baslik.grid(row=0, column=1, sticky="w", pady=(6, 0))
        self.bilgi = tk.Label(self, bg=KART, fg=GRI_KOYU, font=yazi(9), anchor="w")
        self.bilgi.grid(row=1, column=1, sticky="w", pady=(0, 6))
        self.chip = tk.Label(self, font=yazi(9, True), padx=10, pady=3)
        self.chip.grid(row=0, column=2, rowspan=2, padx=10)
        self.cubuk = YuvarlakCubuk(self, 12)
        self.cubuk.grid(row=0, column=3, rowspan=2, sticky="ew", padx=(0, 8))
        self.yuzde = tk.Label(self, bg=KART, fg=METIN, font=yazi(12, True), width=7,
                              anchor="e")
        self.yuzde.grid(row=0, column=4, rowspan=2, padx=(0, 14))
        self.columnconfigure(1, minsize=230)
        self.columnconfigure(3, weight=1, minsize=120)

    def guncelle(self, baslik, durum, soru, katilimci, cevap, yuzde):
        yazi_renk, zemin = DURUM_RENK[durum]
        self.emoji.config(text=DURUM_EMOJI[durum])
        self.baslik.config(text=baslik)
        self.bilgi.config(
            text=f"❓ {soru} soru    👥 {katilimci} katılımcı    💬 {cevap} cevap")
        self.chip.config(text=DURUM_ADI[durum], fg=yazi_renk, bg=zemin)
        self.cubuk.renk = yazi_renk if durum != "beklemede" else GRI
        self.cubuk.ayarla(yuzde)
        self.yuzde.config(text=f"%{yuzde:g}")


class SecenekKarti(tk.Frame):
    """Tıklanabilir şık kartı: harf rozeti + metin. Doğru/yanlış olunca renklenir."""

    def __init__(self, ust, harf, tikla):
        super().__init__(ust, bg=KART, highlightthickness=2,
                         highlightbackground=CIZGI, cursor="hand2")
        self.harf = harf
        self.secili = False
        self.ustunde = False
        self.durum = None  # None, "dogru" veya "yanlis"
        self.rozet = tk.Label(self, text=harf, width=3, font=yazi(12, True))
        self.rozet.pack(side="left", padx=(10, 12), pady=8)
        self.metin = tk.Label(self, text="", font=yazi(13), anchor="w", fg=METIN)
        self.metin.pack(side="left", fill="x", expand=True, pady=8)
        for w in (self, self.rozet, self.metin):
            w.bind("<Button-1>", lambda e: tikla(self.harf))
            w.bind("<Enter>", lambda e: self._ustunde(True))
            w.bind("<Leave>", lambda e: self._ustunde(False))
        self.yenile()

    def _boya(self, zemin, cerceve, rozet_bg, rozet_fg):
        self.config(bg=zemin, highlightbackground=cerceve)
        self.metin.config(bg=zemin)
        self.rozet.config(bg=rozet_bg, fg=rozet_fg)

    def yenile(self):
        if self.durum == "dogru":
            self._boya(YESIL_ACIK, YESIL, YESIL, "white")
        elif self.durum == "yanlis":
            self._boya(KIRMIZI_ACIK, KIRMIZI, KIRMIZI, "white")
        elif self.secili:
            self._boya(MOR_ACIK, MOR, MOR, "white")
        elif self.ustunde:
            self._boya("#f6f4ff", MOR, MOR_ACIK, MOR)
        else:
            self._boya(KART, CIZGI, MOR_ACIK, MOR)

    def _ustunde(self, v):
        self.ustunde = v
        self.yenile()

    def ayarla(self, metin):
        self.metin.config(text=metin)
        self.secili = False
        self.durum = None
        self.yenile()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        font_sec()
        self.title("Quiz Veri Tabanı")
        self.geometry("1060x820")
        self.minsize(940, 700)
        self.configure(bg=ARKA)

        self.kullanici_id = None
        self.oturum_id = None
        self.aktif_soru = None
        self.secili_harf = None
        self.kilit = False          # cevap verildikten sonra kısa bekleme
        self.dogru_sayisi = 0
        self.seri = 0
        self.canli_var = False
        self.nokta_yanik = True
        self.akis = deque(maxlen=6)  # simülasyondaki son cevaplar

        self.stil_ayarla()
        self.baslik_kur()

        self.sekmeler = ttk.Notebook(self)
        self.sekmeler.pack(fill="both", expand=True, padx=10, pady=10)
        self.takip_sekmesi = ttk.Frame(self.sekmeler)
        self.quiz_sekmesi = ttk.Frame(self.sekmeler)
        self.sonuc_sekmesi = ttk.Frame(self.sekmeler)
        self.sekmeler.add(self.takip_sekmesi, text="  📊 Canlı Takip  ")
        self.sekmeler.add(self.quiz_sekmesi, text="  📝 Quiz Çöz  ")
        self.sekmeler.add(self.sonuc_sekmesi, text="  🏆 Sonuçlar  ")

        # Kullanıcı ve oturum listeleri
        self.kullanici_idleri = {ad: kid for kid, ad in sorgu(
            "SELECT id, kullanici_adi FROM kullanicilar ORDER BY id")}
        self.kullanici_adlari = {kid: ad for ad, kid in self.kullanici_idleri.items()}
        self.oturum_etiketleri = [
            f"{oid} - {baslik} ({durum})" for oid, baslik, durum in sorgu(
                "SELECT id, baslik, durum FROM oturumlar ORDER BY id")]

        self.takip_kur()
        self.quiz_kur()
        self.sonuc_kur()

        self.sekmeler.bind("<<NotebookTabChanged>>", lambda e: self.sonuc_yenile())
        self.bind("<Key>", self.tus)
        self.otomatik_yenile()
        self.saat_guncelle()

    # ---------- Görünüm ----------
    def stil_ayarla(self):
        s = ttk.Style(self)
        s.theme_use("clam")  # renk ayarlarının her sistemde çalışması için
        s.configure("TFrame", background=ARKA)
        s.configure("TLabel", background=ARKA, foreground=METIN, font=yazi(10))
        s.configure("TLabelframe", background=ARKA, bordercolor=CIZGI)
        s.configure("TLabelframe.Label", background=ARKA, foreground=METIN,
                    font=yazi(10, True))

        s.configure("TNotebook", background=ARKA, borderwidth=0, tabmargins=(4, 4, 4, 0))
        s.configure("TNotebook.Tab", padding=(18, 10), background=MOR_ACIK,
                    foreground=MOR_KOYU, font=yazi(11, True), borderwidth=0)
        s.map("TNotebook.Tab",
              background=[("selected", MOR), ("active", "#dcd7fb")],
              foreground=[("selected", "white")])

        s.configure("Treeview", rowheight=30, font=yazi(10), background="white",
                    fieldbackground="white", bordercolor=CIZGI, borderwidth=0)
        s.configure("Treeview.Heading", font=yazi(10, True), background=MOR,
                    foreground="white", padding=7, borderwidth=0)
        s.map("Treeview.Heading", background=[("active", MOR_KOYU)])
        s.map("Treeview", background=[("selected", "#c9c2fb")],
              foreground=[("selected", METIN)])

        s.configure("TScrollbar", background=MOR_ACIK, troughcolor=ARKA,
                    bordercolor=ARKA, arrowcolor=MOR, borderwidth=0)
        s.configure("TCombobox", fieldbackground="white", background=MOR_ACIK,
                    arrowcolor=MOR, bordercolor=CIZGI, padding=6)
        s.map("TCombobox", fieldbackground=[("readonly", "white")],
              selectbackground=[("readonly", "white")],
              selectforeground=[("readonly", METIN)])
        self.option_add("*TCombobox*Listbox.font", yazi(10))
        self.option_add("*TCombobox*Listbox.selectBackground", MOR)

        for ad, renk, koyu in (("Mor", MOR, MOR_KOYU),
                               ("Yesil", YESIL, YESIL_KOYU),
                               ("Gri", GRI, GRI_KOYU)):
            s.configure(f"{ad}.TButton", background=renk, foreground="white",
                        font=yazi(10, True), padding=(18, 9), borderwidth=0,
                        focuscolor=renk)
            s.map(f"{ad}.TButton", background=[("active", koyu)])

    def baslik_kur(self):
        """Mordan pembeye geçişli üst başlık, saat ve canlı göstergesi."""
        self.baslik = tk.Canvas(self, height=80, highlightthickness=0, bg=MOR)
        self.baslik.pack(fill="x")
        self.baslik.bind("<Configure>", lambda e: self.baslik_ciz())

    def baslik_ciz(self):
        c = self.baslik
        c.delete("all")
        w, h = c.winfo_width(), 80
        for x in range(0, w, 4):
            c.create_rectangle(x, 0, x + 4, h, outline="",
                               fill=renk_karisim(MOR, PEMBE, x / max(w, 1)))
        c.create_text(24, 30, anchor="w", text="🧠 Quiz Veri Tabanı", fill="white",
                      font=yazi(21, True))
        c.create_text(26, 58, anchor="w",
                      text="SQLite ile oturum takibi, quiz çözme ve sonuçlar",
                      fill="#f4efff", font=yazi(10))
        c.create_text(w - 24, 28, anchor="e", text="", fill="white",
                      font=yazi(14, True), tags="saat")
        c.create_text(w - 24, 54, anchor="e", text="", fill="white",
                      font=yazi(10, True), tags="canli")
        self.baslik_durum_guncelle()

    def baslik_durum_guncelle(self):
        c = self.baslik
        c.itemconfig("saat", text=datetime.now().strftime("%H:%M:%S"))
        if self.canli_var:
            nokta = "●" if self.nokta_yanik else "○"
            c.itemconfig("canli", text=f"{nokta} CANLI OTURUM VAR")
        else:
            c.itemconfig("canli", text="○ canlı oturum yok")

    def saat_guncelle(self):
        self.nokta_yanik = not self.nokta_yanik
        self.baslik_durum_guncelle()
        self.after(1000, self.saat_guncelle)

    # ---------- Canlı Takip ----------
    def takip_kur(self):
        f = self.takip_sekmesi

        # Üstte 4 özet kartı
        kartlar = tk.Frame(f, bg=ARKA)
        kartlar.pack(fill="x", padx=10, pady=(10, 4))
        self.sayi_kartlari = []
        for sutun, (emoji, ad, renk) in enumerate((
                ("👥", "Kullanıcı", MOR), ("📅", "Oturum", TURUNCU),
                ("❓", "Soru", MINT), ("💬", "Cevap", PEMBE))):
            kart = SayiKarti(kartlar, emoji, ad, renk)
            kart.grid(row=0, column=sutun, sticky="nsew", padx=6)
            kartlar.columnconfigure(sutun, weight=1, uniform="sayi")
            self.sayi_kartlari.append(kart)

        # Oturum kartları
        tk.Label(f, text="Oturumların anlık durumu", bg=ARKA, fg=METIN,
                 font=yazi(13, True)).pack(anchor="w", padx=16, pady=(8, 4))
        self.oturum_alani = tk.Frame(f, bg=ARKA)
        self.oturum_alani.pack(fill="x", padx=16)
        self.oturum_kartlari = []

        # Alt kısım: sol canlı panel, sağ son cevaplar
        alt = tk.Frame(f, bg=ARKA)
        alt.pack(fill="both", expand=True, padx=16, pady=(10, 10))
        alt.columnconfigure(0, weight=3, uniform="alt")
        alt.columnconfigure(1, weight=2, uniform="alt")
        alt.rowconfigure(0, weight=1)

        sol = kart_cerceve(alt)
        sol.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.buyuk_etiket = tk.Label(sol, text="", bg=KART, fg=METIN, font=yazi(13, True),
                                     anchor="w")
        self.buyuk_etiket.pack(fill="x", padx=18, pady=(10, 0))
        self.buyuk_mesaj = tk.Label(sol, text="", bg=KART, fg=GRI_KOYU, font=yazi(10),
                                    anchor="w")
        self.buyuk_mesaj.pack(fill="x", padx=18, pady=(0, 6))
        self.buyuk_cubuk = YuvarlakCubuk(sol, 22, renk=MOR)
        self.buyuk_cubuk.pack(fill="x", padx=18)

        dugmeler = tk.Frame(sol, bg=KART)
        dugmeler.pack(fill="x", padx=18, pady=(10, 2))
        ttk.Button(dugmeler, text="⟳ Yenile", style="Mor.TButton",
                   command=self.takip_yenile).pack(side="left")
        self.sim_acik = False
        self.sim_dugme = ttk.Button(dugmeler, text="▶ Canlı simülasyonu başlat",
                                    style="Yesil.TButton",
                                    command=self.simulasyon_degistir)
        self.sim_dugme.pack(side="left", padx=10)
        self.takip_etiket = tk.Label(sol, text="", bg=KART, fg=GRI, font=yazi(9),
                                     anchor="w")
        self.takip_etiket.pack(fill="x", padx=18, pady=(0, 8))

        sag = kart_cerceve(alt)
        sag.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        tk.Label(sag, text="⚡ Son cevaplar", bg=KART, fg=METIN,
                 font=yazi(12, True)).pack(anchor="w", padx=18, pady=(10, 4))
        self.akis_etiket = tk.Label(
            sag, text="Simülasyonu başlatınca\ncevaplar burada akar ✨",
            bg=KART, fg=GRI_KOYU, font=yazi(10), justify="left", anchor="nw")
        self.akis_etiket.pack(fill="both", expand=True, padx=18, pady=(0, 8))

    def takip_yenile(self):
        sayilar = sorgu(SAYILAR_SQL)[0]
        for kart, deger in zip(self.sayi_kartlari, sayilar):
            kart.ayarla(deger)

        satirlar = sorgu(TAKIP_SQL)
        if len(self.oturum_kartlari) != len(satirlar):  # kartları bir kez kur
            for kart in self.oturum_kartlari:
                kart.destroy()
            self.oturum_kartlari = [OturumKarti(self.oturum_alani) for _ in satirlar]
            for kart in self.oturum_kartlari:
                kart.pack(fill="x", pady=2)

        aktif = None
        for kart, satir in zip(self.oturum_kartlari, satirlar):
            kart.guncelle(*satir)
            if satir[1] == "devam_ediyor" and aktif is None:
                aktif = (satir[0], satir[5])

        self.canli_var = aktif is not None
        if aktif:
            baslik, yuzde = aktif
            self.buyuk_etiket.config(text=f"🔥 {baslik} canlı  -  %{yuzde:g} tamamlandı")
            if yuzde >= 100:
                mesaj = "Hepsi tamam, tebrikler 🎉"
            elif yuzde >= 60:
                mesaj = "Bitişe az kaldı 🏁"
            elif yuzde >= 25:
                mesaj = "Hız kesmeden devam 🚀"
            else:
                mesaj = "Yeni başladı 🌱"
            self.buyuk_mesaj.config(text=mesaj)
            self.buyuk_cubuk.ayarla(yuzde)
        else:
            self.buyuk_etiket.config(text="😴 Şu an devam eden oturum yok")
            self.buyuk_mesaj.config(text="Bir oturum başlayınca burada canlı görünür")
            self.buyuk_cubuk.ayarla(0)
        self.baslik_durum_guncelle()
        self.takip_etiket.config(
            text=f"Son güncelleme: {datetime.now().strftime('%H:%M:%S')}  "
                 f"(3 saniyede bir kendiliğinden yenilenir)")

    def simulasyon_degistir(self):
        self.sim_acik = not self.sim_acik
        if self.sim_acik:
            self.sim_dugme.config(text="■ Simülasyonu durdur", style="Gri.TButton")
            self.simulasyon_adimi()
        else:
            self.sim_dugme.config(text="▶ Canlı simülasyonu başlat",
                                  style="Yesil.TButton")

    def simulasyon_adimi(self):
        """Devam eden oturuma her adımda 5 rastgele cevap yazar."""
        if not self.sim_acik:
            return
        satirlar = sorgu(SIM_SQL)
        if not satirlar:
            self.simulasyon_degistir()
            self.takip_yenile()
            messagebox.showinfo(
                "Simülasyon bitti",
                "Devam eden oturumdaki katılımcıların hepsi tüm soruları cevapladı.")
            return
        for kullanici_id, oturum_id, soru_id, dogru in satirlar:
            r = random.random()
            if r < 0.05:
                cevap, em = None, "➖"
            elif r < 0.70:
                cevap, em = dogru, "✅"
            else:
                cevap, em = random.choice([h for h in "ABCD" if h != dogru]), "❌"
            try:
                cevap_kaydet(kullanici_id, oturum_id, soru_id, cevap)
            except sqlite3.Error:
                continue  # veri tabanı reddederse o cevap atlanır
            ad = self.kullanici_adlari.get(kullanici_id, kullanici_id)
            self.akis.appendleft(f"{em}  {ad}  →  soru {soru_id}")
        self.akis_etiket.config(text="\n".join(self.akis), fg=METIN)
        self.takip_yenile()
        self.after(600, self.simulasyon_adimi)

    def otomatik_yenile(self):
        self.takip_yenile()
        self.after(3000, self.otomatik_yenile)

    # ---------- Quiz Çöz ----------
    def quiz_kur(self):
        f = self.quiz_sekmesi

        ust = tk.Frame(f, bg=ARKA)
        ust.pack(fill="x", padx=16, pady=(16, 6))
        ttk.Label(ust, text="👤 Kullanıcı:").grid(row=0, column=0, sticky="w", pady=4)
        self.kullanici_kutu = ttk.Combobox(
            ust, state="readonly", width=22, font=yazi(10),
            values=list(self.kullanici_idleri))
        self.kullanici_kutu.grid(row=0, column=1, padx=10, pady=4)
        ttk.Label(ust, text="📅 Oturum:").grid(row=1, column=0, sticky="w", pady=4)
        self.oturum_kutu = ttk.Combobox(
            ust, state="readonly", width=34, font=yazi(10),
            values=self.oturum_etiketleri)
        self.oturum_kutu.grid(row=1, column=1, padx=10, pady=4)
        ttk.Button(ust, text="Soruyu getir 🚀", style="Mor.TButton",
                   command=self.soru_getir).grid(row=0, column=2, rowspan=2, padx=15)

        # sağda seri ve doğru sayısı
        ust.columnconfigure(3, weight=1)
        rozetler = tk.Frame(ust, bg=ARKA)
        rozetler.grid(row=0, column=3, rowspan=2, sticky="e")
        self.seri_etiket = tk.Label(rozetler, text="🔥 Seri: 0", bg=TURUNCU_ACIK,
                                    fg="#c2610f", font=yazi(11, True), padx=12, pady=6)
        self.seri_etiket.pack(side="left", padx=4)
        self.puan_etiket = tk.Label(rozetler, text="⭐ Doğru: 0", bg=YESIL_ACIK,
                                    fg=YESIL_KOYU, font=yazi(11, True), padx=12, pady=6)
        self.puan_etiket.pack(side="left", padx=4)

        # Soru kartı
        self.kart = kart_cerceve(f)
        self.kart.pack(fill="x", padx=16, pady=10)
        self.soru_no = tk.Label(self.kart, text="", bg=KART, fg=MOR,
                                font=yazi(10, True))
        self.soru_no.pack(anchor="w", padx=20, pady=(16, 0))
        self.soru_etiket = tk.Label(
            self.kart, text="Kullanıcı ve oturum seçip 'Soruyu getir'e bas 👆",
            bg=KART, fg=METIN, font=yazi(17, True), wraplength=880, justify="left")
        self.soru_etiket.pack(anchor="w", padx=20, pady=(6, 12))
        self.kart.bind("<Configure>",
                       lambda e: self.soru_etiket.config(wraplength=max(300, e.width - 60)))

        self.secenek_alani = tk.Frame(self.kart, bg=KART)
        self.secenek_alani.pack(fill="x", padx=20, pady=2)
        self.secenekler = {}
        for harf in "ABCD":
            kart = SecenekKarti(self.secenek_alani, harf, self.sec)
            kart.pack(fill="x", pady=4)
            self.secenekler[harf] = kart

        self.ilerleme_satiri = tk.Frame(self.kart, bg=KART)
        self.ilerleme_satiri.pack(fill="x", padx=20, pady=(12, 4))
        self.ilerleme_cubugu = YuvarlakCubuk(self.ilerleme_satiri, 12, renk=YESIL)
        self.ilerleme_cubugu.pack(side="left", fill="x", expand=True)
        self.ilerleme_etiket = tk.Label(self.ilerleme_satiri, text="", bg=KART,
                                        fg=GRI_KOYU, font=yazi(10))
        self.ilerleme_etiket.pack(side="left", padx=12)

        self.geri_bildirim = tk.Label(self.kart, text=" ", bg=KART, fg=YESIL,
                                      font=yazi(14, True), anchor="w")
        self.geri_bildirim.pack(fill="x", padx=20, pady=(2, 14))

        dugmeler = tk.Frame(f, bg=ARKA)
        dugmeler.pack(anchor="w", padx=16, pady=4)
        ttk.Button(dugmeler, text="Cevapla ✔", style="Yesil.TButton",
                   command=self.cevapla).pack(side="left")
        ttk.Button(dugmeler, text="Boş bırak", style="Gri.TButton",
                   command=lambda: self.cevapla(bos=True)).pack(side="left", padx=10)
        tk.Label(dugmeler, text="⌨  A-D seç  ·  Enter cevapla  ·  Boşluk boş bırak",
                 bg=ARKA, fg=GRI, font=yazi(9)).pack(side="left", padx=14)

    def tus(self, e):
        """Klavye kısayolları (yalnızca Quiz Çöz sekmesinde)."""
        if self.sekmeler.index(self.sekmeler.select()) != 1:
            return
        if isinstance(self.focus_get(), (ttk.Combobox, ttk.Button)):
            return
        tus = e.keysym.upper()
        if tus in ("A", "B", "C", "D"):
            self.sec(tus)
        elif tus == "RETURN":
            self.cevapla()
        elif tus == "SPACE":
            self.cevapla(bos=True)

    def sec(self, harf):
        if self.aktif_soru is None or self.kilit:
            return
        self.focus_set()
        self.secili_harf = harf
        for h, kart in self.secenekler.items():
            kart.secili = (h == harf)
            kart.yenile()

    def istatistik_guncelle(self):
        self.seri_etiket.config(text=f"🔥 Seri: {self.seri}")
        self.puan_etiket.config(text=f"⭐ Doğru: {self.dogru_sayisi}")

    def soru_getir(self):
        kullanici = self.kullanici_kutu.get()
        oturum = self.oturum_kutu.get()
        if not kullanici or not oturum:
            messagebox.showinfo("Bilgi", "Önce kullanıcı ve oturum seç.")
            return
        self.kullanici_id = self.kullanici_idleri[kullanici]
        self.oturum_id = int(oturum.split(" - ")[0])
        self.geri_bildirim.config(text=" ")
        self.kilit = False
        self.seri = 0
        self.dogru_sayisi = sorgu(
            KULLANICI_PUAN_SQL, (self.kullanici_id, self.oturum_id))[0][0]
        self.istatistik_guncelle()
        self.sonraki_soru()
        self.focus_set()  # klavye kısayolları çalışsın

    def sonraki_soru(self):
        satir = sorgu(SONRAKI_SORU_SQL, (self.oturum_id, self.kullanici_id))
        self.secili_harf = None
        toplam, cevaplanan = sorgu(
            ILERLEME_SQL, (self.oturum_id, self.oturum_id, self.kullanici_id))[0]
        self.ilerleme_cubugu.ayarla(100 * cevaplanan / toplam if toplam else 0)
        self.ilerleme_etiket.config(text=f"{cevaplanan} / {toplam} soru")

        if not satir:
            self.aktif_soru = None
            dogru, sayi = sorgu(KULLANICI_PUAN_SQL,
                                (self.kullanici_id, self.oturum_id))[0]
            oran = dogru / sayi if sayi else 0
            if oran >= 0.9:
                emoji, mesaj = "🏆", "Muhteşem!"
            elif oran >= 0.7:
                emoji, mesaj = "🎉", "Harika iş!"
            elif oran >= 0.5:
                emoji, mesaj = "👍", "Fena değil!"
            else:
                emoji, mesaj = "💪", "Bir dahaki sefere daha iyi olacak!"
            self.soru_no.config(text="")
            self.soru_etiket.config(
                text=f"{emoji} {mesaj}\nBu oturumdaki tüm soruları cevapladın.\n"
                     f"Puanın: {dogru} / {sayi}")
            self.secenek_alani.pack_forget()
            return

        soru_id, sira, metin, a, b, c, d = satir[0]
        self.aktif_soru = soru_id
        self.soru_no.config(text=f"  SORU {sira} / {toplam}  ", bg=MOR_ACIK)
        self.soru_etiket.config(text=metin)
        self.secenek_alani.pack(fill="x", padx=20, pady=2, before=self.ilerleme_satiri)
        for harf, secenek in zip("ABCD", (a, b, c, d)):
            self.secenekler[harf].ayarla(secenek)

    def cevapla(self, bos=False):
        if self.kilit:
            return
        if self.aktif_soru is None:
            messagebox.showinfo("Bilgi", "Önce 'Soruyu getir'e bas.")
            return
        cevap = None if bos else self.secili_harf
        if not bos and cevap is None:
            messagebox.showinfo("Bilgi", "Bir şık seç ya da 'Boş bırak'a bas.")
            return
        soru_id = self.aktif_soru
        try:
            cevap_kaydet(self.kullanici_id, self.oturum_id, soru_id, cevap)
        except sqlite3.Error as e:
            messagebox.showerror("Veri tabanı kaydı reddetti", str(e))
            return

        dogru = sorgu("SELECT dogru_cevap FROM sorular WHERE id = ?", (soru_id,))[0][0]
        # şıkları renklendir: doğru yeşil, yanlış seçilen kırmızı
        self.secenekler[dogru].durum = "dogru"
        if cevap is not None and cevap != dogru:
            self.secenekler[cevap].durum = "yanlis"
        for kart in self.secenekler.values():
            kart.yenile()

        if cevap is None:
            self.seri = 0
            self.geri_bildirim.config(text=f"😶 Boş bırakıldı. Doğru cevap: {dogru}",
                                      fg=GRI_KOYU)
        elif cevap == dogru:
            self.seri += 1
            self.dogru_sayisi += 1
            mesaj = random.choice(["Doğru! 🎉", "Harikasın! ✨", "Tam isabet! 🎯",
                                   "Süper! 💜"])
            if self.seri >= 3:
                mesaj += f"  ({self.seri}'li seri 🔥)"
            self.geri_bildirim.config(text=mesaj, fg=YESIL)
        else:
            self.seri = 0
            self.geri_bildirim.config(text=f"😅 Yanlış. Doğru cevap: {dogru}",
                                      fg=KIRMIZI)
        self.istatistik_guncelle()
        self.kilit = True
        self.after(1100, self.devam)

    def devam(self):
        self.kilit = False
        self.sonraki_soru()

    # ---------- Sonuçlar ----------
    def sonuc_kur(self):
        f = self.sonuc_sekmesi
        ust = tk.Frame(f, bg=ARKA)
        ust.pack(fill="x", padx=16, pady=(16, 6))
        ttk.Label(ust, text="📅 Oturum:").pack(side="left")
        self.sonuc_kutu = ttk.Combobox(
            ust, state="readonly", width=34, font=yazi(10),
            values=self.oturum_etiketleri)
        self.sonuc_kutu.pack(side="left", padx=10)
        self.sonuc_kutu.current(0)
        self.sonuc_kutu.bind("<<ComboboxSelected>>", lambda e: self.sonuc_yenile())
        ttk.Button(ust, text="⟳ Yenile", style="Mor.TButton",
                   command=self.sonuc_yenile).pack(side="left")
        self.ozet_etiket = tk.Label(ust, text="", bg=ARKA, fg=GRI_KOYU, font=yazi(10))
        self.ozet_etiket.pack(side="right")

        # İlk üç için podyum kartları
        podyum = tk.Frame(f, bg=ARKA)
        podyum.pack(fill="x", padx=10, pady=(6, 4))
        self.podyum = []
        for sutun, (zemin, cerceve) in enumerate((
                ("#fff4cf", "#f2c84b"), ("#eceef5", "#b9bfd3"), ("#fbe3d0", "#e0a477"))):
            kart = tk.Frame(podyum, bg=zemin, highlightthickness=2,
                            highlightbackground=cerceve)
            kart.grid(row=0, column=sutun, sticky="nsew", padx=6)
            podyum.columnconfigure(sutun, weight=1, uniform="podyum")
            emoji = tk.Label(kart, text="", bg=zemin, font=yazi(26))
            emoji.pack(pady=(8, 0))
            isim = tk.Label(kart, text="-", bg=zemin, fg=METIN, font=yazi(12, True))
            isim.pack()
            puan = tk.Label(kart, text="", bg=zemin, fg=GRI_KOYU, font=yazi(10))
            puan.pack(pady=(0, 8))
            self.podyum.append((emoji, isim, puan, zemin))

        orta = tk.Frame(f, bg=ARKA)
        orta.pack(fill="both", expand=True, padx=15, pady=8)
        orta.columnconfigure(0, weight=1, uniform="tablo")
        orta.columnconfigure(1, weight=1, uniform="tablo")
        orta.rowconfigure(0, weight=1)

        sol = ttk.LabelFrame(orta, text=" 📋 Oturum sonuçları ", padding=8)
        sol.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.sonuc_tablo = tablo_olustur(sol, [
            ("sira", "Sıra", 60), ("kullanici", "Kullanıcı", 120),
            ("dogru", "Doğru", 55), ("yanlis", "Yanlış", 55),
            ("bos", "Boş", 45), ("puan", "Puan", 50)], 10)

        sag = ttk.LabelFrame(orta, text=" 🌟 En yüksek puanlı 10 kullanıcı ", padding=8)
        sag.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.top_tablo = tablo_olustur(sag, [
            ("sira", "Sıra", 60), ("kullanici", "Kullanıcı", 120),
            ("oturum", "Oturum", 65), ("puan", "Toplam Puan", 105)], 10)
        self.sonuc_yenile()

    def sonuc_yenile(self):
        oturum = self.sonuc_kutu.get()
        if oturum:
            oturum_id = int(oturum.split(" - ")[0])
            satirlar = sorgu(SONUC_SQL, (oturum_id,))
            tablo_doldur(self.sonuc_tablo, satirlar)
            self.podyum_guncelle(satirlar)
        tablo_doldur(self.top_tablo, sorgu(TOP10_SQL))

    def podyum_guncelle(self, satirlar):
        for i, (emoji, isim, puan, _) in enumerate(self.podyum):
            if i < len(satirlar):
                sira, ad, dogru = satirlar[i][0], satirlar[i][1], satirlar[i][2]
                emoji.config(text=MADALYA.get(sira, "🎖️"))
                isim.config(text=ad)
                puan.config(text=f"{dogru} puan")
            else:
                emoji.config(text="")
                isim.config(text="-")
                puan.config(text="")
        if satirlar:
            puanlar = [s[5] for s in satirlar]
            self.ozet_etiket.config(
                text=f"👥 {len(satirlar)} katılımcı    📈 ortalama {sum(puanlar) / len(puanlar):.1f}"
                     f"    🏆 en yüksek {max(puanlar)}")
        else:
            self.ozet_etiket.config(text="Bu oturumda henüz cevap yok 🌱")


if __name__ == "__main__":
    App().mainloop()