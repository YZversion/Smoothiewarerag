from __future__ import annotations

import csv
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    cloc_p = root / "logs" / "cloc_by_file_smoothieware.csv"
    fb_p = root / "logs" / "corpus_recon_by_file_smoothieware_r620e1622972b_v3.csv"

    cloc = {}
    with cloc_p.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            fn = (row.get("filename") or "").replace("\\", "/").strip()
            if not fn or fn == "SUM":
                continue
            key = fn.split("repos/Smoothieware/", 1)[-1] if "repos/Smoothieware/" in fn else fn
            cloc[key] = {
                "code": int(row.get("code") or 0),
                "comment": int(row.get("comment") or 0),
                "blank": int(row.get("blank") or 0),
            }

    fb = {}
    with fb_p.open(encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            key = row["path"].replace("\\", "/")
            fb[key] = {
                "code": int(row["code"]),
                "comment": int(row["comment"]),
                "blank": int(row["blank"]),
            }

    keys = sorted(set(fb) & set(cloc))
    miss = len(set(fb) - set(cloc))
    extra = len(set(cloc) - set(fb))

    ct = {"code": 0, "comment": 0, "blank": 0}
    ft = {"code": 0, "comment": 0, "blank": 0}
    rows = []
    for k in keys:
        c = cloc[k]
        b = fb[k]
        dc = b["code"] - c["code"]
        dm = b["comment"] - c["comment"]
        db = b["blank"] - c["blank"]
        abs_sum = abs(dc) + abs(dm) + abs(db)
        rows.append((abs_sum, k, dc, dm, db, c, b))
        for t in ("code", "comment", "blank"):
            ct[t] += c[t]
            ft[t] += b[t]
    rows.sort(reverse=True)

    out = root / "notes" / "corpus_recon_calibration.md"
    lines = [
        "# Corpus Recon Calibration (fallback vs cloc)",
        "",
        "- Corpus: `repos/Smoothieware`",
        "- cloc install method: `winget install --id AlDanial.Cloc --source winget`",
        "- cloc executable path: `C:/Users/14390/AppData/Local/Microsoft/WinGet/Packages/AlDanial.Cloc_Microsoft.Winget.Source_8wekyb3d8bbwe/cloc.exe`",
        "- Scope: common target-extension files only",
        "",
        "## Total Comparison",
        "",
        "| Metric | cloc | fallback | delta | deviation |",
        "|------|-----:|---------:|-------:|-----:|",
    ]
    for t in ("code", "comment", "blank"):
        c = ct[t]
        b = ft[t]
        d = b - c
        p = (abs(d) / c * 100 if c else 0.0)
        lines.append(f"| {t} | {c:,} | {b:,} | {d:+,} | {p:.2f}% |")

    ctot = sum(ct.values())
    ftot = sum(ft.values())
    dd = ftot - ctot
    pp = abs(dd) / ctot * 100 if ctot else 0.0
    lines.append(f"| total | {ctot:,} | {ftot:,} | {dd:+,} | {pp:.2f}% |")
    lines += [
        "",
        f"- file matching: common={len(keys)}, fallback_only={miss}, cloc_only={extra}",
        "",
        "## By-file Delta Top 10 (|dCode|+|dComment|+|dBlank|)",
        "",
        "| File | dCode | dComment | dBlank | cloc(total) | fallback(total) |",
        "|------|------:|---------:|-------:|------------:|---------------:|",
    ]
    for _abs, k, dc, dm, db, c, b in rows[:10]:
        lines.append(
            f"| `{k}` | {dc:+} | {dm:+} | {db:+} | "
            f"{c['code'] + c['comment'] + c['blank']:,} | "
            f"{b['code'] + b['comment'] + b['blank']:,} |"
        )
    max_col_dev = max(
        abs(ft["code"] - ct["code"]) / ct["code"] * 100 if ct["code"] else 0.0,
        abs(ft["comment"] - ct["comment"]) / ct["comment"] * 100 if ct["comment"] else 0.0,
        abs(ft["blank"] - ct["blank"]) / ct["blank"] * 100 if ct["blank"] else 0.0,
    )
    lines += ["", "## Verdict", ""]
    if max_col_dev < 2.0:
        lines.append(
            f"- max(code/comment/blank) deviation {max_col_dev:.2f}% < 2%, **fallback is acceptable**."
        )
    else:
        lines.append(
            f"- max(code/comment/blank) deviation {max_col_dev:.2f}% >= 2%, fallback parsing needs fixes."
        )

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out}")
    print(f"total_deviation_pct={pp:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
