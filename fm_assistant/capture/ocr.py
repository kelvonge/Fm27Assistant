"""OCR local et gratuit : RapidOCR (modèles embarqués, hors ligne) puis OCR de Windows en secours."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

log = logging.getLogger("fma.ocr")


@dataclass
class Token:
    """Un mot lu à l'écran, avec sa boîte en pixels (coin haut-gauche)."""
    text: str
    x: float
    y: float
    w: float
    h: float
    conf: float = 1.0

    @property
    def x1(self) -> float:
        return self.x + self.w

    @property
    def y1(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def as_dict(self) -> dict:
        return {"t": self.text, "x": round(self.x), "y": round(self.y), "w": round(self.w), "h": round(self.h), "c": round(self.conf, 2)}


def _box_to_token(text: str, box, conf: float) -> Token | None:
    text = (text or "").strip()
    if not text:
        return None
    xs = [float(p[0]) for p in box]
    ys = [float(p[1]) for p in box]
    return Token(text, min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys), float(conf))


class RapidOcr3:
    """Paquet « rapidocr » (v2/v3) : accents gérés, boîtes mot à mot."""
    name = "RapidOCR"

    def __init__(self):
        from rapidocr import RapidOCR  # type: ignore

        logging.getLogger("RapidOCR").setLevel(logging.ERROR)
        self._engine = RapidOCR()

    def read(self, img: np.ndarray) -> list[Token]:
        try:
            res = self._engine(img, use_cls=False, return_word_box=True)
        except TypeError:
            res = self._engine(img)
        out: list[Token] = []
        words = getattr(res, "word_results", None)
        if words:
            for line in words:
                for item in line:
                    tok = _box_to_token(item[0], item[2], item[1])
                    if tok:
                        out.append(tok)
            return out
        boxes, txts, scores = getattr(res, "boxes", None), getattr(res, "txts", None), getattr(res, "scores", None)
        if boxes is None or txts is None:
            return out
        for box, txt, sc in zip(boxes, txts, scores or [1.0] * len(txts)):
            tok = _box_to_token(txt, box, sc)
            if tok:
                out.append(tok)
        return out


class RapidOcrLegacy:
    """Ancien paquet « rapidocr_onnxruntime » (lit moins bien les accents)."""
    name = "RapidOCR (ancienne version)"

    def __init__(self):
        from rapidocr_onnxruntime import RapidOCR  # type: ignore

        self._engine = RapidOCR()

    def read(self, img: np.ndarray) -> list[Token]:
        result, _ = self._engine(img)
        out = []
        for box, txt, sc in result or []:
            tok = _box_to_token(txt, box, float(sc))
            if tok:
                out.append(tok)
        return out


class WindowsOcr:
    """OCR intégré à Windows 10/11 (paquets winrt). Secours si RapidOCR est absent."""
    name = "OCR Windows"

    def __init__(self):
        from winrt.windows.globalization import Language  # type: ignore
        from winrt.windows.media.ocr import OcrEngine  # type: ignore

        engine = None
        for tag in ("fr-FR", "fr", "en-US", "en-GB"):
            lang = Language(tag)
            if OcrEngine.is_language_supported(lang):
                engine = OcrEngine.try_create_from_language(lang)
                if engine:
                    break
        engine = engine or OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            raise RuntimeError("Aucune langue OCR installée dans Windows")
        self._engine = engine

    def read(self, img: np.ndarray) -> list[Token]:
        import asyncio

        import cv2
        from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap  # type: ignore
        from winrt.windows.storage.streams import DataWriter  # type: ignore

        bgra = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        h, w = bgra.shape[:2]
        writer = DataWriter()
        writer.write_bytes(bgra.tobytes())
        bitmap = SoftwareBitmap.create_copy_from_buffer(writer.detach_buffer(), BitmapPixelFormat.BGRA8, w, h)

        async def run():
            return await self._engine.recognize_async(bitmap)

        result = asyncio.run(run())
        out = []
        for line in result.lines:
            for word in line.words:
                r = word.bounding_rect
                if word.text.strip():
                    out.append(Token(word.text.strip(), r.x, r.y, r.width, r.height, 0.9))
        return out


_ENGINES = {"rapidocr": (RapidOcr3, RapidOcrLegacy), "windows": (WindowsOcr,)}


class Ocr:
    """Choisit le premier moteur disponible et garde la raison de l'échec sinon."""

    def __init__(self, preference: str = "auto"):
        self.engine = None
        self.errors: list[str] = []
        order = ["rapidocr", "windows"] if preference in ("auto", "rapidocr", "", None) else [preference, "rapidocr"]
        for key in order:
            for cls in _ENGINES.get(key, ()):
                try:
                    self.engine = cls()
                    log.info("Moteur OCR : %s", self.engine.name)
                    return
                except Exception as exc:  # moteur absent ou cassé : on essaie le suivant
                    self.errors.append(f"{cls.name} : {exc}")

    @property
    def available(self) -> bool:
        return self.engine is not None

    @property
    def name(self) -> str:
        return self.engine.name if self.engine else "aucun"

    def read(self, img: np.ndarray, scale: float = 0.0) -> list[Token]:
        """Lit une image BGR. scale=0 → agrandissement automatique des petites captures."""
        if self.engine is None:
            return []
        import cv2

        if img.ndim == 3 and img.shape[2] == 4:
            img = img[:, :, :3]
        h = img.shape[0]
        if not scale:
            scale = 1.0 if h >= 1000 else (1.35 if h >= 800 else 1.7)
        work = img
        if abs(scale - 1.0) > 0.01:
            work = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        tokens = self.engine.read(np.ascontiguousarray(work))
        if abs(scale - 1.0) > 0.01:
            for t in tokens:
                t.x /= scale; t.y /= scale; t.w /= scale; t.h /= scale
        return tokens
