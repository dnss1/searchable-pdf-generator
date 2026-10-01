"""OCR 인식 품질 지표."""
from __future__ import annotations

import difflib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

QUOTE_MAP = str.maketrans({
    "“": '"', "”": '"', "‘": "'", "’": "'",
})


def normalize(text: str, nfkc: bool = False) -> str:
    if nfkc:
        text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text.translate(QUOTE_MAP)).strip()


def strip_spaces(text: str) -> str:
    return re.sub(r"\s+", "", text)


def levenshtein(a, b) -> int:
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, n + 1):
            cur = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
            prev = cur
    return dp[n]


@dataclass
class Accumulator:
    gt_chars: int = 0
    char_edit: int = 0
    gt_chars_ns: int = 0          # ns = no space
    char_edit_ns: int = 0
    gt_words: int = 0
    word_edit: int = 0
    exact: int = 0
    units: int = 0
    tp: int = 0
    fp: int = 0
    fn: int = 0
    neds: list = field(default_factory=list)
    errors: Counter = field(default_factory=Counter)

    def add(self, gt: str, pred: str, classify: bool = False) -> None:
        g, p = normalize(gt), normalize(pred)
        self.units += 1
        self.gt_chars += len(g)
        self.char_edit += levenshtein(g, p)

        gns, pns = strip_spaces(g), strip_spaces(p)
        self.gt_chars_ns += len(gns)
        self.char_edit_ns += levenshtein(gns, pns)

        gw, pw = g.split(), p.split()
        self.gt_words += len(gw)
        self.word_edit += levenshtein(gw, pw)

        if g == p:
            self.exact += 1
        self.neds.append(difflib.SequenceMatcher(None, g, p).ratio())

        gc, pc = Counter(gw), Counter(pw)
        tp = sum((gc & pc).values())
        self.tp += tp
        self.fp += sum(pc.values()) - tp
        self.fn += sum(gc.values()) - tp

        if classify and g != p:
            self.errors[classify_error(g, p)] += 1

    def merge(self, other: "Accumulator") -> None:
        for f in ("gt_chars", "char_edit", "gt_chars_ns", "char_edit_ns",
                  "gt_words", "word_edit", "exact", "units", "tp", "fp", "fn"):
            setattr(self, f, getattr(self, f) + getattr(other, f))
        self.neds.extend(other.neds)
        self.errors.update(other.errors)

    def result(self) -> dict:
        cer = self.char_edit / max(self.gt_chars, 1)
        cer_ns = self.char_edit_ns / max(self.gt_chars_ns, 1)
        wer = self.word_edit / max(self.gt_words, 1)
        prec = self.tp / max(self.tp + self.fp, 1)
        rec = self.tp / max(self.tp + self.fn, 1)
        out = {
            "units": self.units,
            "cer": cer,
            "char_acc": 1 - cer,
            "char_acc_nospace": 1 - cer_ns,
            "wer": wer,
            "word_acc": max(0.0, 1 - wer),
            "exact_acc": self.exact / max(self.units, 1),
            "precision": prec,
            "recall": rec,
            "f1": 2 * prec * rec / max(prec + rec, 1e-9),
            "ned": sum(self.neds) / max(len(self.neds), 1),
        }
        if self.errors:
            total = max(self.units, 1)
            out["error_types"] = {
                k: {"count": v, "ratio": v / total}
                for k, v in sorted(self.errors.items(), key=lambda x: -x[1])
            }
        return out


SIMILAR = [
    ("–", "-"), ("—", "-"), ("−", "-"),      # dash 계열
    ("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'),
    ("〈", "<"), ("〉", ">"), ("＜", "<"), ("＞", ">"),
    ("Ⅰ", "I"), ("Ⅱ", "II"), ("Ⅲ", "III"),
    ("Ⅳ", "IV"), ("Ⅴ", "V"), ("Ⅵ", "VI"),
]


def _fold_similar(s: str) -> str:
    for a, b in SIMILAR:
        s = s.replace(a, b)
    return s


def classify_error(gt: str, pred: str) -> str:
    if strip_spaces(gt) == strip_spaces(pred):
        return "spacing_only"
    if strip_spaces(_fold_similar(gt)) == strip_spaces(_fold_similar(pred)):
        return "substitution"
    g, p = strip_spaces(gt), strip_spaces(pred)
    if len(p) < len(g):
        return "missing"
    if len(p) > len(g):
        return "overgen"
    return "substitution"


BIAS_SYMBOLS = "△▲▷▶∼―·○●〜°"


def bias_symbol_counts(gt_text: str, pred_text: str, symbols: str = BIAS_SYMBOLS) -> dict:
    gc, pc = Counter(gt_text), Counter(pred_text)
    return {c: {"gt": gc.get(c, 0), "pred": pc.get(c, 0)} for c in symbols}
