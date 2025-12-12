#!/usr/bin/env python3
"""
SVGGradientRemover.py

Replace SVG linearGradient fills with a solid color (taken from the first stop),
write the modified SVG, then convert it to PDF using svglib + ReportLab.

Why: svglib/ReportLab do not support SVG color gradients. :contentReference[oaicite:1]{index=1}
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import xml.etree.ElementTree as ET

from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg


_LOG = logging.getLogger(__name__)

# Matches: url(#gradId), url('#gradId'), url("#gradId") with arbitrary whitespace
_URL_REF_RE = re.compile(r"""^url\(\s*['"]?#(?P<id>[^'")\s]+)['"]?\s*\)\s*$""")


@dataclass(frozen=True)
class Paths:
    input_svg: Path
    output_svg: Path
    output_pdf: Path


def _register_common_namespaces(root: ET.Element) -> None:
    """
    Helps ElementTree write output without introducing 'ns0' prefixes when possible.
    """
    # Default namespace (e.g. {http://www.w3.org/2000/svg}svg)
    if root.tag.startswith("{"):
        ns = root.tag.split("}", 1)[0][1:]
        ET.register_namespace("", ns)

    # Common xlink namespace (used by some SVGs for href)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


def _parse_style(style: str) -> dict[str, str]:
    """
    Parse a CSS style attribute into a dict. Keeps last occurrence of duplicate keys.
    """
    out: dict[str, str] = {}
    for chunk in style.split(";"):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        k, v = chunk.split(":", 1)
        out[k.strip()] = v.strip()
    return out


def _format_style(style_map: dict[str, str]) -> str:
    """
    Convert a style dict back to a style string.
    """
    # Stable output (use insertion order; dict preserves it in Py3.7+)
    return "; ".join(f"{k}: {v}" for k, v in style_map.items() if k and v) + (";" if style_map else "")


def _extract_stop_color(stop_elem: ET.Element) -> Optional[str]:
    """
    Extract stop color from <stop stop-color="..."> or <stop style="stop-color:...">.
    """
    color = stop_elem.get("stop-color")
    if color:
        return color.strip()

    style = stop_elem.get("style")
    if style:
        style_map = _parse_style(style)
        color = style_map.get("stop-color")
        if color:
            return color.strip()

    return None


def _first_gradient_color(gradient: ET.Element, gradient_by_id: dict[str, ET.Element]) -> Optional[str]:
    """
    Return the first stop-color for a gradient, following href references if needed.
    """
    # Try direct stops
    for child in list(gradient):
        if child.tag.endswith("stop"):
            color = _extract_stop_color(child)
            if color:
                return color

    # Some gradients reference another gradient via href/xlink:href
    href = (
        gradient.get("{http://www.w3.org/1999/xlink}href")
        or gradient.get("href")
        or gradient.get("{http://www.w3.org/1999/xlink}HREF")
        or gradient.get("HREF")
    )
    if href and href.startswith("#"):
        ref_id = href[1:]
        ref = gradient_by_id.get(ref_id)
        if ref is not None and ref is not gradient:
            return _first_gradient_color(ref, gradient_by_id)

    return None


def _is_fill_url_ref(value: str, gradient_id: str) -> bool:
    m = _URL_REF_RE.match(value.strip())
    return bool(m and m.group("id") == gradient_id)


def _replace_fill_attributes(root: ET.Element, gradient_id: str, solid_color: str) -> int:
    """
    Replace occurrences of fill="url(#gradient_id)" (and the same in style="...") with solid_color.
    Returns the number of replacements performed.
    """
    replacements = 0

    for elem in root.iter():
        # 1) Direct fill attribute
        fill = elem.get("fill")
        if fill and _is_fill_url_ref(fill, gradient_id):
            elem.set("fill", solid_color)
            replacements += 1

        # 2) fill inside style="..."
        style = elem.get("style")
        if style:
            style_map = _parse_style(style)
            style_fill = style_map.get("fill")
            if style_fill and _is_fill_url_ref(style_fill, gradient_id):
                style_map["fill"] = solid_color
                elem.set("style", _format_style(style_map))
                replacements += 1

    return replacements


def _find_linear_gradients(root: ET.Element) -> list[ET.Element]:
    """
    Find <linearGradient> elements within any <defs>.
    """
    return root.findall(".//{*}defs/{*}linearGradient")


def process_svg(input_svg: Path, output_svg: Path) -> None:
    tree = ET.parse(input_svg)
    root = tree.getroot()

    _register_common_namespaces(root)

    gradients = _find_linear_gradients(root)
    if not gradients:
        _LOG.info("No <linearGradient> found under <defs>; writing SVG unchanged.")
    else:
        # Build id -> gradient map for href resolution
        gradient_by_id: dict[str, ET.Element] = {}
        for g in gradients:
            gid = g.get("id")
            if gid:
                gradient_by_id[gid] = g

        for gradient in gradients:
            gid = gradient.get("id")
            if not gid:
                _LOG.warning("Skipping <linearGradient> without id.")
                continue

            color = _first_gradient_color(gradient, gradient_by_id)
            if not color:
                _LOG.warning("Gradient '%s' has no stop-color; skipping.", gid)
                continue

            n = _replace_fill_attributes(root, gid, color)
            _LOG.info("Replaced %d occurrence(s) of url(#%s) with '%s'.", n, gid, color)

    # Pretty-indent if available (Python 3.9+)
    if hasattr(ET, "indent"):
        try:
            ET.indent(tree, space="  ")
        except Exception:
            # Non-fatal; keep going with unindented output
            pass

    # Write with XML declaration and UTF-8 encoding. :contentReference[oaicite:2]{index=2}
    tree.write(output_svg, encoding="utf-8", xml_declaration=True)


def convert_svg_to_pdf(input_svg: Path, output_pdf: Path) -> None:
    drawing = svg2rlg(str(input_svg))
    # ReportLab renderer writes Drawing into a PDF file. :contentReference[oaicite:3]{index=3}
    renderPDF.drawToFile(drawing, str(output_pdf))


def _parse_args(argv: Optional[list[str]] = None) -> Paths:
    p = argparse.ArgumentParser(
        description="Replace SVG linearGradient fills with solid colors and convert to PDF."
    )
    p.add_argument(
        "--input",
        dest="input_svg",
        default="Graphs-Screenshot.svg",
        help="Input SVG path (default: Graphs-Screenshot.svg)",
    )
    p.add_argument(
        "--output-svg",
        dest="output_svg",
        default="newSVG.svg",
        help="Output SVG path (default: newSVG.svg)",
    )
    p.add_argument(
        "--output-pdf",
        dest="output_pdf",
        default="Graphs-Screenshot.pdf",
        help="Output PDF path (default: Graphs-Screenshot.pdf)",
    )
    args = p.parse_args(argv)

    return Paths(
        input_svg=Path(args.input_svg),
        output_svg=Path(args.output_svg),
        output_pdf=Path(args.output_pdf),
    )


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    paths = _parse_args(argv)

    if not paths.input_svg.exists():
        _LOG.error("Input SVG not found: %s", paths.input_svg)
        return 2

    try:
        process_svg(paths.input_svg, paths.output_svg)
        convert_svg_to_pdf(paths.output_svg, paths.output_pdf)
    except ET.ParseError as e:
        _LOG.error("Failed to parse SVG/XML: %s", e)
        return 3
    except Exception as e:
        _LOG.exception("Failed: %s", e)
        return 1

    _LOG.info("Wrote: %s", paths.output_svg)
    _LOG.info("Wrote: %s", paths.output_pdf)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
