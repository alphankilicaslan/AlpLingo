import os
import json

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# Desteklenen Kaynak Diller (NLLB-200 + Özel OCR Grupları)
SUPPORTED_LANGUAGES = {
    "Japonca": {
        "display": "Japonca (日本語)",
        "nllb_code": "jpn_Jpan",
        "ocr_group": "japan",
        "no_space_join": True,
    },
    "İngilizce": {
        "display": "İngilizce (English)",
        "nllb_code": "eng_Latn",
        "ocr_group": "en",
        "no_space_join": False,
    },
    "Almanca": {
        "display": "Almanca (Deutsch)",
        "nllb_code": "deu_Latn",
        "ocr_group": "latin",
        "no_space_join": False,
    },
    "Fransızca": {
        "display": "Fransızca (Français)",
        "nllb_code": "fra_Latn",
        "ocr_group": "latin",
        "no_space_join": False,
    },
    "İspanyolca": {
        "display": "İspanyolca (Español)",
        "nllb_code": "spa_Latn",
        "ocr_group": "latin",
        "no_space_join": False,
    },
    "İtalyanca": {
        "display": "İtalyanca (Italiano)",
        "nllb_code": "ita_Latn",
        "ocr_group": "latin",
        "no_space_join": False,
    },
    "Portekizce": {
        "display": "Portekizce (Português)",
        "nllb_code": "por_Latn",
        "ocr_group": "latin",
        "no_space_join": False,
    },
    "Lehçe": {
        "display": "Lehçe (Polski)",
        "nllb_code": "pol_Latn",
        "ocr_group": "latin",
        "no_space_join": False,
    },
    "Hollandaca": {
        "display": "Hollandaca (Nederlands)",
        "nllb_code": "nld_Latn",
        "ocr_group": "latin",
        "no_space_join": False,
    },
    "Rusça": {
        "display": "Rusça (Русский)",
        "nllb_code": "rus_Cyrl",
        "ocr_group": "cyrillic",
        "no_space_join": False,
    },
    "Ukraynaca": {
        "display": "Ukraynaca (Українська)",
        "nllb_code": "ukr_Cyrl",
        "ocr_group": "cyrillic",
        "no_space_join": False,
    },
    "Korece": {
        "display": "Korece (한국어)",
        "nllb_code": "kor_Hang",
        "ocr_group": "korean",
        "no_space_join": False,
    },
    "Çince (Basitleştirilmiş)": {
        "display": "Çince - Basitleştirilmiş (简体中文)",
        "nllb_code": "zho_Hans",
        "ocr_group": "ch_sim",
        "no_space_join": True,
    },
    "Çince (Geleneksel)": {
        "display": "Çince - Geleneksel (繁體中文)",
        "nllb_code": "zho_Hant",
        "ocr_group": "ch_tra",
        "no_space_join": True,
    },
    "Arapça": {
        "display": "Arapça (العربية)",
        "nllb_code": "ara_Arab",
        "ocr_group": "arabic",
        "no_space_join": False,
    },
}

DEFAULT_CONFIG = {
    # Ekran Okuma Alanı (Varsayılan olarak ekranın alt-orta diyalog bölgesi)
    "capture_area": {
        "x": 400,
        "y": 750,
        "width": 1120,
        "height": 200
    },
    # Altyazı Penceresi Konumu ve Boyutu
    "overlay_position": {
        "x": 400,
        "y": 600,
        "width": 1120,
        "height": 130
    },
    # Yazı Stili & Tipografi
    "font_family": "Segoe UI",
    "font_size": 20,
    "font_weight": "Bold",       # Normal, Medium, Bold, ExtraBold, Black
    "text_color": "#FFFFFF",      # Beyaz
    "outline_color": "#000000",   # Siyah kenar çizgisi (okunabilirlik için)
    "outline_width": 2,           # Kenar kalınlığı
    "bg_color": "#000000",        # Arka plan kutusu
    "bg_opacity": 120,            # 0-255 (Yarı saydam)
    "alignment": "Left",          # Left (Oyun diyalog yapısı), Center, Right
    
    # Kısayol Tuşu (Açma / Kapatma)
    # hotkey_type: "keyboard" veya "mouse"
    # sol tık (left click) ASLA seçilemez!
    "hotkey_type": "keyboard",
    "hotkey_value": "f9",
    "hotkey_display": "Tuş: F9",
    
    # Kaynak Dil (SUPPORTED_LANGUAGES anahtarlarından biri)
    "source_lang": "Japonca",

    # Çalışma Modu
    "auto_scan": True,            # Sürekli otomatik çeviri
    "scan_interval_ms": 300,      # Tarama sıklığı (ms - pürüzsüz oyun performansı)
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in data:
                        data[k] = v
                if data.get("source_lang") not in SUPPORTED_LANGUAGES:
                    data["source_lang"] = "Japonca"
                return data
        except Exception as e:
            print(f"Ayar dosyası okuma hatası: {e}. Varsayılanlar yükleniyor.")
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()

def save_config(config_dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_dict, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Ayar kaydetme hatası: {e}")
        return False

def reset_to_defaults():
    config = DEFAULT_CONFIG.copy()
    save_config(config)
    return config
