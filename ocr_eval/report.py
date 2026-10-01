"""결과 → 마크다운 표."""
from __future__ import annotations

COLS = [
    ("char_acc", "Char Acc"),
    ("char_acc_nospace", "공백제거"),
    ("f1", "F1"),
    ("exact_acc", "Exact"),
    ("ned", "NED"),
    ("cer", "CER"),
    ("wer", "WER"),
]


def _pct(v):
    return f"{v * 100:.2f}"


def markdown(result: dict, title: str = "평가 결과") -> str:
    per = result.get("per_domain", {})
    out = [f"# {title}", ""]

    head = "| 도메인 | 단위 | " + " | ".join(n for _, n in COLS) + " |"
    sep = "|---|---:|" + "---:|" * len(COLS)
    out += [head, sep]
    for dom, m in per.items():
        row = [dom, str(m["units"])] + [_pct(m[k]) for k, _ in COLS]
        out.append("| " + " | ".join(row) + " |")

    ov = result["overall"]
    out.append("| **전체** | **" + str(ov["units"]) + "** | "
               + " | ".join(f"**{_pct(ov[k])}**" for k, _ in COLS) + " |")
    out.append("")

    et = ov.get("error_types")
    if et:
        out += ["## 오류 유형", "",
                "| 유형 | 건수 | 비율 | 해석 |", "|---|---:|---:|---|"]
        meaning = {
            "spacing_only": "공백만 다름 — 대개 **정답 라벨** 쪽 문제",
            "substitution": "유사 문자 치환 (dash·로마숫자 등)",
            "missing": "누락 — 예측이 더 짧음",
            "overgen": "과생성 — 예측이 더 김",
        }
        for k, v in et.items():
            out.append(f"| `{k}` | {v['count']} | {v['ratio'] * 100:.2f}% | {meaning.get(k, '')} |")
        out.append("")
    return "\n".join(out)
