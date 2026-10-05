#!/usr/bin/env python3
"""Kaggle nisanyansozluk.com dump (output.json) -> Apple Dictionary Development
Kit XML (Dictionary.xml) for the "Nişanyan Sözlük" macOS Dictionary bundle.
"""
import json
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

from lxml import etree
from lxml import html as lhtml

ROOT = Path(__file__).resolve().parent.parent
SRC_JSON = ROOT / "data" / "raw" / "extracted" / "output.json"
OUT_XML = ROOT / "data" / "processed" / "NisanyanSozluk.xml"

SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def clean_fragment(raw_html: str) -> str:
    """Parse a scraped HTML fragment leniently, strip dead internal links and
    hidden helper spans, and return well-formed inner XHTML markup."""
    if not raw_html or not raw_html.strip():
        return ""
    wrapper = lhtml.fragment_fromstring(raw_html, create_parent="div")

    for span in wrapper.xpath('.//span[contains(@style, "visibility:hidden")]'):
        span.drop_tree()
    for a in wrapper.xpath(".//a"):
        a.drop_tag()

    inner = "".join(
        etree.tostring(child, encoding="unicode", method="xml")
        for child in wrapper.iterchildren()
    )
    if wrapper.text and wrapper.text.strip():
        inner = escape(wrapper.text) + inner
    return inner.strip()


def split_headword(key: str) -> tuple[str, str | None]:
    """'ağ1' -> ('ağ', '1'); 'abart-' -> ('abart-', None)."""
    if key and key[-1].isdigit():
        i = len(key)
        while i > 0 and key[i - 1].isdigit():
            i -= 1
        return key[:i], key[i:]
    return key, None


def build_entry(key: str, e: dict) -> str:
    base, num = split_headword(key)
    display_title = base + (num.translate(SUPERSCRIPT) if num else "")

    koken = clean_fragment(e["koken"])
    ek = clean_fragment(e["ek_aciklama"])
    tarihce = clean_fragment(e["tarihce"])

    turevler: list[str] = []
    for field in ("benzer_sozcukler", "maddeye_gonderenler"):
        val = e.get(field)
        if isinstance(val, list):
            turevler.extend(val)
    # de-dupe, keep order
    seen = set()
    turevler = [w for w in turevler if not (w in seen or seen.add(w))]

    sections = []
    if koken:
        sections.append(f'<div class="ns_section"><h3>Köken</h3>{koken}</div>')
    if ek:
        sections.append(f'<div class="ns_section"><h3>Ek açıklama</h3>{ek}</div>')
    if tarihce:
        sections.append(f'<div class="ns_section"><h3>Tarihçe</h3>{tarihce}</div>')
    if turevler:
        items = "".join(f"<li>{escape(w)}</li>" for w in turevler)
        sections.append(
            "<div class=\"ns_section\"><h3>Türevler, bileşikler, deyimler</h3>"
            f"<ul>{items}</ul></div>"
        )
    body = "\n".join(sections)

    id_attr = quoteattr(key)
    title_attr = quoteattr(display_title)
    index_attr = quoteattr(base)

    entry = (
        f"<d:entry id={id_attr} d:title={title_attr}>\n"
        f"<d:index d:value={index_attr}/>\n"
    )
    if num:
        # also index the raw disambiguated form (e.g. "ağ1") as a fallback
        entry += f"<d:index d:value={quoteattr(key)}/>\n"
    entry += f"<h1>{escape(display_title)}</h1>\n{body}\n</d:entry>"
    return entry


def main() -> None:
    if not SRC_JSON.is_file():
        raise SystemExit(f"Veri bulunamadı: {SRC_JSON}. README'deki Kaggle indirme adımını tamamlayın.")
    with open(SRC_JSON, encoding="utf-8") as f:
        data = json.load(f)

    entries = []
    errors = []
    for key, e in data.items():
        try:
            entries.append(build_entry(key, e))
        except Exception as exc:  # noqa: BLE001
            errors.append((key, repr(exc)))

    header = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<d:dictionary xmlns="http://www.w3.org/1999/xhtml" '
        'xmlns:d="http://www.apple.com/DTDs/DictionaryService-1.0.rng">\n'
    )
    footer = "\n</d:dictionary>\n"

    if errors:
        for key, err in errors[:20]:
            print(f"  {key}: {err}")
        raise SystemExit(f"{len(errors)} madde dönüştürülemedi; eksik sözlük üretilmedi.")
    etree.fromstring((header + "\n".join(entries) + footer).encode("utf-8"))
    OUT_XML.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_XML, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(entries))
        f.write(footer)

    print(f"wrote {len(entries)} entries -> {OUT_XML}")
    if errors:
        print(f"{len(errors)} entries failed:")
        for key, err in errors[:20]:
            print(f"  {key}: {err}")

    # sanity check: the output must itself be well-formed XML
    etree.parse(str(OUT_XML))
    print("XML well-formed check: OK")


if __name__ == "__main__":
    main()
