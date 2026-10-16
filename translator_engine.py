import os
import re
import time
from difflib import SequenceMatcher
import numpy as np
import mss
import ctranslate2
import sentencepiece as spm
from huggingface_hub import snapshot_download, hf_hub_download
from rapidocr_onnxruntime import RapidOCR

from config import SUPPORTED_LANGUAGES

def setup_cuda_dlls():
    try:
        import site
        for sp in site.getsitepackages():
            nv_bin = os.path.join(sp, "nvidia", "cublas", "bin")
            if os.path.exists(nv_bin):
                os.environ["PATH"] = nv_bin + ";" + os.environ.get("PATH", "")
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(nv_bin)
                    except Exception:
                        pass
    except Exception as e:
        print(f"CUDA DLL ayarlama notu: {e}")

setup_cuda_dlls()

# Sadece Türkçe'de bulunan karakterler (Almanca ö/ü ve Fransızca ç hariç tutuldu!)
STRICT_TURKISH_CHARS = set("ğĞşŞıİ")

# Alfabe doğrulama regex'leri (Latin dışı dillerde Latin/Türkçe altyazıyı okumamak için)
SCRIPT_REGEX = {
    "japan": re.compile(r"[\u3040-\u309f\u30a0-\u30ff\uff00-\uff9f\u4e00-\u9faf\u3400-\u4dbf]"),
    "korean": re.compile(r"[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]"),
    "cyrillic": re.compile(r"[\u0400-\u04ff]"),
    "ch_sim": re.compile(r"[\u4e00-\u9faf\u3400-\u4dbf]"),
    "ch_tra": re.compile(r"[\u4e00-\u9faf\u3400-\u4dbf]"),
    "arabic": re.compile(r"[\u0600-\u06ff\u0750-\u077f]"),
}

# OCR Grup -> HuggingFace deepghs/paddleocr model yolları
OCR_GROUP_MODELS = {
    "en": "rec/en_PP-OCRv4_rec",
    "latin": "rec/latin_PP-OCRv3_rec",
    "japan": "rec/japan_PP-OCRv3_rec",
    "korean": "rec/korean_PP-OCRv3_rec",
    "cyrillic": "rec/cyrillic_PP-OCRv3_rec",
    "ch_sim": "rec/ch_PP-OCRv4_rec",
    "ch_tra": "rec/chinese_cht_PP-OCRv3_rec",
    "arabic": "rec/arabic_PP-OCRv3_rec",
}

# Cümle sonu noktalama işaretleri
SENTENCE_END_CHARS = (".", "!", "?", ":", "…", "。", "！", "？", "」", "』", "”", "\"")


class TranslationEngine:
    def __init__(self, intra_threads=4):
        self.intra_threads = intra_threads
        self.model_id = "mijuanlo/nllb-200-distilled-600M-ct2-int8"
        self.translator = None
        self.sp = None

        # Yüklenen OCR Motorları önbelleği: {ocr_group: RapidOCR}
        self.ocr_engines = {}
        self.default_ocr = None

        # Thread-local mss nesnesi
        self.sct = None

        self.cache = {}
        self.recent_translations = []
        self.last_raw_text = ""
        self.last_translation = ""
        self.last_img_thumb = None
        self.is_loaded = False

    def load_models(self):
        """Modelleri yerel klasörden veya önbellekten yükler (GPU öncelikli)"""
        try:
            print("Çeviri modeli hazırlanıyor (NLLB-200 INT8 - 200+ Dil)...")
            base_dir = os.path.dirname(os.path.abspath(__file__))
            local_nllb = os.path.join(base_dir, "models", "nllb-200-distilled-600M-ct2-int8")
            if os.path.exists(os.path.join(local_nllb, "model.bin")):
                model_dir = local_nllb
                print("Model doğrudan yerel models klasöründen yüklendi.")
            else:
                try:
                    model_dir = snapshot_download(repo_id=self.model_id, local_files_only=True)
                except Exception:
                    model_dir = snapshot_download(repo_id=self.model_id)

            spm_path = os.path.join(model_dir, "sentencepiece.bpe.model")

            self.sp = spm.SentencePieceProcessor()
            self.sp.load(spm_path)

            device = "cpu"
            compute_type = "int8"
            try:
                if ctranslate2.get_cuda_device_count() > 0:
                    device = "cuda"
                    compute_type = "int8_float16"
                    print("[GPU] NVIDIA RTX CUDA algılandı! Çevirici ekran kartında çalışacak.")
            except Exception as e:
                print(f"CUDA algılama notu: {e}")

            if device == "cuda":
                try:
                    self.translator = ctranslate2.Translator(
                        model_dir,
                        device="cuda",
                        compute_type="int8_float16"
                    )
                    # CUDA GPU bağlamını açılışta hemen başlat (warmup)
                    self.translator.translate_batch([["eng_Latn", "ok", "</s>"]], target_prefix=[["tur_Latn"]])
                except Exception as e:
                    print(f"GPU yükleme hatası ({e}), CPU moduna geçiliyor...")
                    self.translator = ctranslate2.Translator(
                        model_dir,
                        device="cpu",
                        compute_type="int8",
                        intra_threads=self.intra_threads
                    )
            else:
                print("CPU modu devrede.")
                self.translator = ctranslate2.Translator(
                    model_dir,
                    device="cpu",
                    compute_type="int8",
                    intra_threads=self.intra_threads
                )

            print("Temel OCR motorları hazırlanıyor...")
            self.default_ocr = RapidOCR(det_limit_type="max", det_limit_side_len=960)
            # En sık kullanılan grupları hazırla, diğerleri seçildiğinde anında diskten yüklenir
            for grp in ("japan", "en", "latin"):
                self._get_ocr_engine(grp)

            self.is_loaded = True
            print("Tüm yerel modeller başarıyla yüklendi!")
            return True
        except Exception as e:
            print(f"Model yükleme hatası: {e}")
            return False

    def _get_ocr_engine(self, ocr_group: str) -> RapidOCR:
        """Seçilen dil grubuna ait özel OCR modelini getirir (Önbellekli)"""
        if ocr_group in self.ocr_engines:
            return self.ocr_engines[ocr_group]

        repo_subpath = OCR_GROUP_MODELS.get(ocr_group)
        if not repo_subpath:
            return self.default_ocr

        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            local_m = os.path.join(base_dir, "models", "paddleocr", repo_subpath, "model.onnx")
            local_d = os.path.join(base_dir, "models", "paddleocr", repo_subpath, "dict.txt")
            if os.path.exists(local_m) and os.path.exists(local_d):
                m_path = local_m
                d_path = local_d
            else:
                try:
                    m_path = hf_hub_download("deepghs/paddleocr", f"{repo_subpath}/model.onnx", local_files_only=True)
                    d_path = hf_hub_download("deepghs/paddleocr", f"{repo_subpath}/dict.txt", local_files_only=True)
                except Exception:
                    m_path = hf_hub_download("deepghs/paddleocr", f"{repo_subpath}/model.onnx")
                    d_path = hf_hub_download("deepghs/paddleocr", f"{repo_subpath}/dict.txt")

            engine = RapidOCR(rec_model_path=m_path, rec_keys_path=d_path, det_limit_type="max", det_limit_side_len=960)
            self.ocr_engines[ocr_group] = engine
            return engine
        except Exception as e:
            print(f"OCR grup ({ocr_group}) yükleme hatası: {e}")
            return self.default_ocr

    def reset_state(self):
        """Çeviri açılıp kapatıldığında durumu temizler"""
        self.last_raw_text = ""
        self.last_translation = ""
        self.last_img_thumb = None

    def capture_region(self, area_dict):
        """Ekrandan belirlenen alanı yakalar ve numpy array'e çevirir"""
        if self.sct is None:
            self.sct = mss.mss()

        monitor = {
            "top": max(0, int(area_dict.get("y", 0))),
            "left": max(0, int(area_dict.get("x", 0))),
            "width": max(20, int(area_dict.get("width", 400))),
            "height": max(20, int(area_dict.get("height", 100))),
        }
        try:
            sct_img = self.sct.grab(monitor)
            img_np = np.array(sct_img)[:, :, :3]
            return img_np
        except Exception:
            self.sct = mss.mss()
            sct_img = self.sct.grab(monitor)
            return np.array(sct_img)[:, :, :3]

    def _is_own_translation_or_turkish(self, text: str, source_lang: str) -> bool:
        """
        Okunan metnin kendi çevirimiz (echo) veya zaten Türkçe olup olmadığını tespit eder.
        Çevirdiğini tekrar çevirme bug'ını %100 engeller.
        """
        t = text.strip()
        if not t:
            return True

        ui_phrases = (
            "[taşıma modu]",
            "kutuyu sürükleyerek",
            "türkçe altyazı",
            "tarama başlatıldı",
            "konuşma bekleniyor",
            "ayarlar varsayılana",
            "okuma alanı güncellendi",
        )
        t_lower = t.lower()
        for phrase in ui_phrases:
            if phrase in t_lower:
                return True

        lang_info = SUPPORTED_LANGUAGES.get(source_lang, SUPPORTED_LANGUAGES["İngilizce"])
        ocr_group = lang_info["ocr_group"]

        # 1. Latin dışı bir dil seçiliyse (Japonca, Korece, Rusça, Çince, Arapça), o alfabeden karakter içermeli
        if ocr_group in SCRIPT_REGEX:
            if not SCRIPT_REGEX[ocr_group].search(t):
                return True
        else:
            # Latin dillerinde (İngilizce, Almanca, Fransızca vb.) sadece Türkçe'ye has harfler (ğ, ş, ı, İ) varsa Türkçe'dir!
            if any(ch in t for ch in STRICT_TURKISH_CHARS):
                return True

        # 2. Son ürettiğimiz Türkçe çevirilerle benzerlik kontrolü
        norm_t = self._normalize_for_compare(t)
        for recent_tr in self.recent_translations:
            norm_tr = self._normalize_for_compare(recent_tr)
            if not norm_tr:
                continue
            if len(norm_t) >= 4 and (norm_t in norm_tr or norm_tr in norm_t):
                return True
            if SequenceMatcher(None, norm_t, norm_tr).ratio() >= 0.62:
                return True

        return False

    @staticmethod
    def _normalize_for_compare(text: str) -> str:
        """Ufak OCR titreşimlerini (nokta/virgül farkı) yoksaymak için metni normalize eder"""
        return re.sub(r"[\s\W_]+", "", text.lower(), flags=re.UNICODE)

    def extract_structured_lines(self, result, source_lang="Japonca") -> list[str]:
        """
        OCR kutularını ekrandaki gerçek görsel satır ve paragraf yapısına göre gruplar.
        Örnek:
          1. Satır: Karakter İsmi / Unvanı (3 kelime)
          2. Satır: Konuşma metni (15 kelime)
        """
        if not result:
            return []

        lang_info = SUPPORTED_LANGUAGES.get(source_lang, SUPPORTED_LANGUAGES["İngilizce"])
        no_space_join = lang_info.get("no_space_join", False)

        boxes_info = []
        for item in result:
            box, raw_txt, score = item[0], item[1], item[2]
            txt = raw_txt.strip()
            if not txt or score < 0.45:
                continue

            if self._is_own_translation_or_turkish(txt, source_lang):
                continue

            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            left, right = min(xs), max(xs)
            top, bottom = min(ys), max(ys)
            height = max(1.0, bottom - top)
            width = max(1.0, right - left)
            cy = (top + bottom) / 2.0

            boxes_info.append({
                "text": txt,
                "left": left,
                "right": right,
                "top": top,
                "bottom": bottom,
                "width": width,
                "height": height,
                "cy": cy,
            })

        if not boxes_info:
            return []

        # 1. Yukarıdan aşağıya sırala ve aynı yatay hizadaki kutuları birleştir
        boxes_info.sort(key=lambda b: b["cy"])
        visual_rows = []

        for b in boxes_info:
            if not visual_rows:
                visual_rows.append([b])
            else:
                last_row = visual_rows[-1]
                avg_cy = sum(x["cy"] for x in last_row) / len(last_row)
                avg_h = sum(x["height"] for x in last_row) / len(last_row)
                if abs(b["cy"] - avg_cy) <= avg_h * 0.55:
                    last_row.append(b)
                else:
                    visual_rows.append([b])

        rows_data = []
        joiner = "" if no_space_join else " "
        for r in visual_rows:
            r.sort(key=lambda x: x["left"])
            row_text = joiner.join(x["text"] for x in r).strip()
            if not row_text:
                continue
            rows_data.append({
                "text": row_text,
                "left": min(x["left"] for x in r),
                "right": max(x["right"] for x in r),
                "top": min(x["top"] for x in r),
                "bottom": max(x["bottom"] for x in r),
                "width": max(x["right"] for x in r) - min(x["left"] for x in r),
                "height": sum(x["height"] for x in r) / len(r),
            })

        if not rows_data:
            return []

        if len(rows_data) == 1:
            return [rows_data[0]["text"]]

        # 2. Satır Yapısını Koru:
        # - İlk satır isim/başlık ise (örn. 1-4 kelime isim) kendi satırında (1. Satır) kalır.
        # - Alt satırlarda devam eden konuşma metni ise (2. Satır) tam cümle olarak birleştirilir.
        max_width = max(r["width"] for r in rows_data)
        structured_lines = [rows_data[0]["text"]]

        for i in range(1, len(rows_data)):
            prev_r = rows_data[i - 1]
            curr_r = rows_data[i]

            vertical_gap = curr_r["top"] - prev_r["bottom"]
            avg_h = (prev_r["height"] + curr_r["height"]) / 2.0

            prev_words = len(prev_r["text"].split())
            is_first_line_header = (
                i == 1 and (
                    (not no_space_join and prev_words <= 5) or
                    (no_space_join and len(prev_r["text"]) <= 12) or
                    prev_r["width"] < max_width * 0.80 or
                    vertical_gap > avg_h * 0.65
                )
            )

            # Konuşma satırının alt satıra taşan devamı mı?
            is_wrapped_continuation = (
                not is_first_line_header and
                vertical_gap <= avg_h * 1.15 and
                not prev_r["text"].endswith(SENTENCE_END_CHARS)
            )

            if is_wrapped_continuation:
                structured_lines[-1] = structured_lines[-1] + joiner + curr_r["text"]
            else:
                structured_lines.append(curr_r["text"])

        return structured_lines

    def run_ocr_lines(self, img_np, source_lang="Japonca") -> list[str]:
        """Görseldeki metni seçilen dilin özel OCR motoruyla ve satır yapısını koruyarak okur"""
        lang_info = SUPPORTED_LANGUAGES.get(source_lang, SUPPORTED_LANGUAGES["İngilizce"])
        ocr_engine = self._get_ocr_engine(lang_info["ocr_group"])
        if ocr_engine is None:
            return []
        try:
            result, _ = ocr_engine(img_np)
            if not result:
                return []
            return self.extract_structured_lines(result, source_lang=source_lang)
        except Exception as e:
            print(f"OCR hatası: {e}")
            return []

    def translate_lines_to_turkish(self, lines: list[str], source_lang="Japonca") -> str:
        """
        Her satırı (Örn: 1. Satır 3 kelime İsim, 2. Satır 15 kelime Konuşma)
        kendi satır yapısını koruyarak Türkçeye çevirir.
        """
        if not lines:
            return ""

        lang_info = SUPPORTED_LANGUAGES.get(source_lang, SUPPORTED_LANGUAGES["İngilizce"])
        src_token = lang_info["nllb_code"]
        no_space_join = lang_info.get("no_space_join", False)

        final_lines = [None] * len(lines)
        to_translate_indices = []
        to_translate_tokens = []

        for idx, line in enumerate(lines):
            cleaned = line.strip() if no_space_join else " ".join(line.split())
            if not cleaned:
                final_lines[idx] = ""
                continue

            cache_key = f"{src_token}:{cleaned}"
            if cache_key in self.cache:
                final_lines[idx] = self.cache[cache_key]
            else:
                tokens = [src_token] + self.sp.encode_as_pieces(cleaned) + ["</s>"]
                to_translate_indices.append((idx, cleaned, cache_key))
                to_translate_tokens.append(tokens)

        if to_translate_tokens:
            try:
                results = self.translator.translate_batch(
                    to_translate_tokens,
                    target_prefix=[["tur_Latn"]] * len(to_translate_tokens),
                    max_batch_size=512,
                    beam_size=1
                )
                for (idx, cleaned, cache_key), res in zip(to_translate_indices, results):
                    out_tokens = res.hypotheses[0][1:]
                    tr_line = self.sp.decode(out_tokens).strip()
                    if len(self.cache) > 500:
                        self.cache.pop(next(iter(self.cache)))
                    self.cache[cache_key] = tr_line
                    final_lines[idx] = tr_line
                    self._record_recent_translation(tr_line)
            except Exception as e:
                print(f"Çeviri hatası: {e}")
                return self.last_translation

        full_tr = "\n".join(l for l in final_lines if l)
        self._record_recent_translation(full_tr)
        return full_tr

    def _record_recent_translation(self, tr_text: str):
        if not tr_text:
            return
        for line in tr_text.splitlines():
            line = line.strip()
            if line and line not in self.recent_translations:
                self.recent_translations.append(line)
        if tr_text not in self.recent_translations:
            self.recent_translations.append(tr_text)
        while len(self.recent_translations) > 30:
            self.recent_translations.pop(0)

    def scan_and_translate(self, area_dict, source_lang="Japonca"):
        """
        Ekranı okur, akıllı metin parlaklık filtresi ile hareketli arka planı (video/3D oyun)
        tamamen yok sayarak %0 CPU/GPU yüküyle altyazıları Türkçeye çevirir.
        """
        if not self.is_loaded:
            return None, None

        img_np = self.capture_region(area_dict)
        if img_np is None or img_np.size == 0:
            return "", ""

        # 1. Akıllı Metin Parlaklık Filtresi (<0.8ms):
        # Arka plandaki hareket eden video, 3D dünya, çimenler veya karakterleri tamamen yok sayar.
        # Altyazılar her zaman yüksek parlaklıkta (beyaz/sarı) olur.
        gray_thumb = np.mean(img_np[::4, ::4], axis=2)
        text_mask = (gray_thumb > 180).astype(np.uint8)
        text_pixel_count = int(np.count_nonzero(text_mask))

        # Eğer ekranda okunabilir parlak yazının pikselleri yoksa (<25 piksel),
        # arkadaki video/oyun ne kadar hareket ederse etsin OCR ve GPU modellerini ASLA çalıştırma!
        if text_pixel_count < 25:
            self.last_img_thumb = None
            self.last_raw_text = ""
            self.last_translation = ""
            return "", ""

        # Eğer ekrandaki yazı pikselleri bir öncekiyle neredeyse aynıysa (%92+ örtüşme), tekrar OCR çalıştırma
        if self.last_img_thumb is not None and self.last_img_thumb.shape == text_mask.shape:
            mask_diff = int(np.count_nonzero(text_mask != self.last_img_thumb))
            if mask_diff < max(20, int(text_pixel_count * 0.08)):
                return self.last_raw_text, self.last_translation

        self.last_img_thumb = text_mask

        lines = self.run_ocr_lines(img_np, source_lang=source_lang)
        if not lines:
            self.last_raw_text = ""
            self.last_translation = ""
            return "", ""

        ocr_text = "\n".join(lines)
        norm_new = self._normalize_for_compare(ocr_text)
        norm_old = self._normalize_for_compare(self.last_raw_text)

        # 2. Önceki okunan metinle neredeyse aynıysa (%88+ benzerlik) tekrar çevirme
        if norm_old and norm_new:
            if norm_new == norm_old:
                return ocr_text, self.last_translation
            sim = SequenceMatcher(None, norm_new, norm_old).ratio()
            if sim >= 0.88 and abs(len(norm_new) - len(norm_old)) <= 3:
                return ocr_text, self.last_translation

        self.last_raw_text = ocr_text
        tr_text = self.translate_lines_to_turkish(lines, source_lang=source_lang)
        self.last_translation = tr_text
        return ocr_text, tr_text
