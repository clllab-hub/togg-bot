"""
Togg T10X Stok Kontrolü — GitHub Actions sürümü
Her çalıştığında siteyi bir kez kontrol eder, stok geldiyse Telegram'a yazar.
Bot token ve chat ID kodda DEĞİL, GitHub "Secrets" bölümünde saklanır.
"""

import os
import json
from datetime import datetime, timezone, timedelta

import requests

# ======================= AYARLAR =======================
TARGET_URL = ""  # Kontrol edilecek adres (birlikte bulacağız)

# text_absent  -> CHECK_TEXT yazısı KAYBOLURSA stok var sayılır
# text_present -> CHECK_TEXT yazısı GÖRÜNÜRSE stok var sayılır
# json         -> JSON_PATH alanı JSON_EXPECTED değerine eşitse stok var
CHECK_MODE = "text_absent"
CHECK_TEXT = "Stokta yok"
JSON_PATH = ""
JSON_EXPECTED = "true"
# =======================================================

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
REQUEST_COOKIE = os.environ.get("REQUEST_COOKIE", "")
REQUEST_AUTH = os.environ.get("REQUEST_AUTH", "")
TEST_MESAJI = os.environ.get("TEST_MESAJI", "") == "true"

DURUM_DOSYASI = "durum.json"
SITE = "https://configurator.togg.com.tr/"


def telegram(metin: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("TELEGRAM_BOT_TOKEN veya TELEGRAM_CHAT_ID secret'ı eksik.")
        return
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": metin},
        timeout=15,
    )
    if not r.ok:
        print("Telegram hatası:", r.text)


def durum_oku() -> dict:
    try:
        with open(DURUM_DOSYASI, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def durum_yaz(durum: dict) -> None:
    with open(DURUM_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(durum, f, ensure_ascii=False, indent=2)


def stok_var_mi(r: requests.Response) -> bool:
    mod = CHECK_MODE.lower()
    if mod == "text_absent":
        return CHECK_TEXT.lower() not in r.text.lower()
    if mod == "text_present":
        return CHECK_TEXT.lower() in r.text.lower()
    if mod == "json":
        veri = r.json()
        for k in JSON_PATH.split("."):
            veri = veri[int(k)] if isinstance(veri, list) else veri[k]
        return str(veri).lower() == JSON_EXPECTED.lower()
    raise ValueError(f"Bilinmeyen CHECK_MODE: {CHECK_MODE}")


def main() -> None:
    if TEST_MESAJI:
        telegram("✅ Test başarılı! GitHub botu sana mesaj gönderebiliyor.")

    if not TARGET_URL:
        print("TARGET_URL boş. kontrol.py içindeki AYARLAR bölümünü doldur.")
        return

    durum = durum_oku()
    basliklar = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9",
    }
    if REQUEST_COOKIE:
        basliklar["Cookie"] = REQUEST_COOKIE
    if REQUEST_AUTH:
        basliklar["Authorization"] = REQUEST_AUTH

    try:
        r = requests.get(TARGET_URL, headers=basliklar, timeout=20)
        if r.status_code in (401, 403):
            if not durum.get("yetki_uyarisi"):
                telegram(f"⚠️ Site erişimi reddetti ({r.status_code}). Oturum bilgisi "
                         "yenilenmeli ya da site yurt dışı sunucuları engelliyor olabilir.")
                durum["yetki_uyarisi"] = True
                durum_yaz(durum)
            return
        r.raise_for_status()
        stok = stok_var_mi(r)
    except Exception as e:
        durum["hata_sayisi"] = durum.get("hata_sayisi", 0) + 1
        print("Kontrol hatası:", e)
        if durum["hata_sayisi"] == 3:
            telegram(f"⚠️ Üst üste 3 kontrol başarısız: {e}")
        durum_yaz(durum)
        return

    onceki = durum.get("son_durum")
    print("Stok durumu:", "VAR ✅" if stok else "yok")

    if stok and onceki != "var":
        saat = datetime.now(timezone(timedelta(hours=3))).strftime("%H:%M")
        for _ in range(3):
            telegram(f"🚨 T10X STOK GELDİ! ({saat})\nHemen uygulamaya / siteye gir!\n{SITE}")
    elif not stok and onceki == "var":
        telegram("ℹ️ Stok tekrar tükendi, takip devam ediyor.")

    yeni = {"son_durum": "var" if stok else "yok"}
    if yeni != durum:
        durum_yaz(yeni)


if __name__ == "__main__":
    main()
