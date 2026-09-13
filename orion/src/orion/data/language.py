"""Language identification.

Two detectors share one interface (``detect(text) -> (label, confidence)``):

* ``ScriptDetector`` — Unicode-script statistics plus stop-word voting for a handful of major
  Latin- and Cyrillic-script languages. Real but coarse: it always reports a script, and a
  language only when the stop-word evidence is clear; otherwise ``und_<Script>``. Reported as
  ``lang_method="script"``.
* ``GlotLIDDetector`` — GlotLID v3 (fastText, 2,102 labels, Apache-2.0 plus notices) when the
  model file and ``fasttext-wheel`` are installed. Reported as ``lang_method="glotlid"``.

Labels follow the GlotLID / FLORES convention ``<iso639-3>_<Script>``, e.g. ``eng_Latn``.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from .schema import Record, RecordStage
from .text import words

# (inclusive code-point ranges) -> ISO 15924 script code
SCRIPT_RANGES: list[tuple[int, int, str]] = [
    (0x0041, 0x024F, "Latn"), (0x1E00, 0x1EFF, "Latn"),
    (0x0370, 0x03FF, "Grek"),
    (0x0400, 0x052F, "Cyrl"),
    (0x0530, 0x058F, "Armn"),
    (0x0590, 0x05FF, "Hebr"),
    (0x0600, 0x06FF, "Arab"), (0x0750, 0x077F, "Arab"), (0x08A0, 0x08FF, "Arab"),
    (0xFB50, 0xFDFF, "Arab"), (0xFE70, 0xFEFF, "Arab"),
    (0x0900, 0x097F, "Deva"), (0x0980, 0x09FF, "Beng"), (0x0A00, 0x0A7F, "Guru"),
    (0x0A80, 0x0AFF, "Gujr"), (0x0B80, 0x0BFF, "Taml"), (0x0C00, 0x0C7F, "Telu"),
    (0x0C80, 0x0CFF, "Knda"), (0x0D00, 0x0D7F, "Mlym"),
    (0x0E00, 0x0E7F, "Thai"), (0x0E80, 0x0EFF, "Laoo"), (0x0F00, 0x0FFF, "Tibt"),
    (0x1000, 0x109F, "Mymr"), (0x10A0, 0x10FF, "Geor"), (0x1200, 0x137F, "Ethi"),
    (0x1780, 0x17FF, "Khmr"),
    (0x1100, 0x11FF, "Hang"), (0x3130, 0x318F, "Hang"), (0xAC00, 0xD7AF, "Hang"),
    (0x3040, 0x309F, "Hira"), (0x30A0, 0x30FF, "Kana"),
    (0x3400, 0x4DBF, "Hani"), (0x4E00, 0x9FFF, "Hani"), (0xF900, 0xFAFF, "Hani"),
    (0x20000, 0x2A6DF, "Hani"),
]

# Function words that distinguish major languages within a script. Deliberately short lists:
# the goal is a confident label for common languages and an honest "und" otherwise.
STOPWORDS: dict[str, dict[str, set[str]]] = {
    "Latn": {
        "eng": {"the", "and", "of", "to", "is", "in", "that", "it", "with", "for", "was", "are", "this", "not"},
        "spa": {"el", "la", "de", "que", "y", "los", "las", "en", "un", "una", "es", "por", "con", "para"},
        "fra": {"le", "la", "les", "de", "des", "et", "est", "un", "une", "que", "pour", "dans", "qui", "pas"},
        "deu": {"der", "die", "das", "und", "ist", "nicht", "ein", "eine", "mit", "sich", "auf", "den", "von", "zu"},
        "por": {"o", "a", "os", "as", "de", "que", "e", "do", "da", "em", "um", "uma", "para", "com", "não"},
        "ita": {"il", "la", "di", "che", "e", "è", "un", "una", "per", "non", "con", "del", "della", "sono"},
        "nld": {"de", "het", "een", "en", "van", "is", "dat", "niet", "op", "met", "zijn", "voor", "ook", "maar"},
        "ind": {"yang", "dan", "di", "dengan", "untuk", "ini", "itu", "dari", "adalah", "tidak", "pada", "akan"},
        "tur": {"ve", "bir", "bu", "için", "ile", "da", "de", "olarak", "çok", "daha", "gibi", "ama", "ne"},
        "vie": {"và", "của", "là", "có", "không", "được", "trong", "cho", "này", "với", "những", "một"},
        "pol": {"i", "w", "nie", "się", "na", "z", "do", "to", "że", "jest", "jak", "ale", "od", "po"},
    },
    "Cyrl": {
        "rus": {"и", "в", "не", "на", "что", "с", "это", "как", "по", "но", "из", "он", "от", "для"},
        "ukr": {"і", "в", "не", "на", "що", "з", "це", "як", "але", "від", "для", "до", "та", "його"},
        "bul": {"и", "в", "на", "не", "се", "за", "да", "с", "от", "че", "по", "това", "са", "като"},
    },
}


def script_of(ch: str) -> str | None:
    cp = ord(ch)
    for lo, hi, name in SCRIPT_RANGES:
        if lo <= cp <= hi:
            return name
    return None


def script_profile(text: str, limit: int = 4000) -> tuple[Counter[str], int]:
    """Counts of alphabetic characters per script (unknown scripts counted as 'Zyyy')."""
    counts: Counter[str] = Counter()
    n = 0
    for ch in text[:limit]:
        if ch.isalpha():
            n += 1
            counts[script_of(ch) or "Zyyy"] += 1
    return counts, n


class ScriptDetector:
    method = "script"

    def detect(self, text: str) -> tuple[str, float]:
        counts, n = script_profile(text)
        if n == 0:
            return "und_Zyyy", 0.0
        script, top = counts.most_common(1)[0]
        frac = top / n
        # Japanese uses Han + kana; Korean is Hangul; Han alone is Chinese (variety unknown).
        kana = counts["Hira"] + counts["Kana"]
        if kana > 0 and (kana + counts["Hani"]) / n > 0.5:
            return "jpn_Jpan", round((kana + counts["Hani"]) / n, 3)
        if script == "Hang":
            return "kor_Hang", round(frac, 3)
        if script == "Hani":
            return "zho_Hani", round(frac, 3)
        table = STOPWORDS.get(script)
        if not table:
            return f"und_{script}", round(frac, 3)
        ws = Counter(words(text[:4000]))
        votes = sorted(((sum(ws[w] for w in sw), lang) for lang, sw in table.items()), reverse=True)
        best = votes[0]
        second = votes[1] if len(votes) > 1 else (0, "")
        if best[0] >= 3 and best[0] >= 1.5 * max(1, second[0]):
            margin = 1 - second[0] / best[0]
            return f"{best[1]}_{script}", round(frac * (0.5 + 0.5 * margin), 3)
        return f"und_{script}", round(frac, 3)


class GlotLIDDetector:
    method = "glotlid"

    def __init__(self, model_path: str | Path):
        try:
            import fasttext  # provided by fasttext-wheel
        except ImportError as e:  # pragma: no cover - depends on optional install
            raise ImportError("GlotLID needs `fasttext-wheel` (pip install fasttext-wheel)") from e
        path = Path(model_path)
        if not path.exists():
            raise FileNotFoundError(f"GlotLID model not found: {path} (cis-lmu/glotlid model_v3.bin)")
        self.model = fasttext.load_model(str(path))

    def detect(self, text: str) -> tuple[str, float]:
        labels, probs = self.model.predict(text.replace("\n", " ")[:2000], k=1)
        return labels[0].replace("__label__", ""), round(float(probs[0]), 4)


class LanguageStage(RecordStage):
    """Annotate ``lang``/``lang_conf``/``lang_method``; drop unidentifiable or disallowed text."""

    name = "language"

    def __init__(self, detector=None, allowed: set[str] | None = None, min_script_frac: float = 0.5):
        self.detector = detector or ScriptDetector()
        self.allowed = allowed
        self.min_script_frac = min_script_frac

    def apply(self, r: Record) -> None:
        counts, n = script_profile(r.text)
        if n == 0:
            return r.drop(self.name, "no alphabetic characters")
        if counts.most_common(1)[0][1] / n < self.min_script_frac:
            return r.drop(self.name, "no dominant script (mixed or garbled text)")
        lang, conf = self.detector.detect(r.text)
        r.meta.update(lang=lang, lang_conf=conf, lang_method=self.detector.method)
        if self.allowed is not None and lang not in self.allowed and lang.split("_")[0] not in self.allowed:
            r.drop(self.name, f"language {lang} not in allowed set")
