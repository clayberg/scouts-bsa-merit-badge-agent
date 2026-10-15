#!/usr/bin/env python3
"""Render inline Markdown Mermaid diagrams to high-DPI PNGs and sync to Google Docs.

Why this script exists:
- Google Docs does not natively render ```mermaid fenced code blocks, and the default
  mermaid2dot post-processor in the gdocs CLI strips emojis, chokes on <br/> tags or
  bidirectional <--> arrows, and can hit shared Docs API read quota limits.
- This script parses all ```mermaid flowchart blocks across the repository's .md files,
  converts them via Graphviz (dot -Tsvg) + Headless Chrome (--force-device-scale-factor=2)
  into crisp, Scout-branded PNG images in docs/images/mermaid-*.png, substitutes those
  image links into a temporary .gdoc-sync.md file, and imports the document into Google
  Docs in a single atomic Drive HTML/Markdown update pass.

Usage:
  # 1. Render all Mermaid diagrams across .md files to docs/images/mermaid-*.png
  python3 scripts/sync_markdown_with_mermaid_to_gdocs.py --render-only

  # 2. Render and sync all companion Google Docs (or a specific doc via --only)
  python3 scripts/sync_markdown_with_mermaid_to_gdocs.py --sync-gdocs
  python3 scripts/sync_markdown_with_mermaid_to_gdocs.py --sync-gdocs --only docs/USER_GUIDE.md
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
import re
import subprocess
import tempfile
import time
from PIL import Image, ImageChops

REPO_ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = REPO_ROOT / "docs" / "images"
GDOCS_BIN = "/google/bin/releases/gemini-agents-gdocs/gdocs"
CHROME_BIN = "/usr/bin/google-chrome"

# Mapping of repository Markdown files to their companion Google Doc IDs
COMPANION_GDOCS: dict[str, str] = {
    "docs/USER_GUIDE.md": "1IYMvIW_72EFoA5wr4h1I4mPXyCm0k6RmRbnlv9z5dHo",
    "docs/ADMIN_GUIDE.md": "1jCQclVI2KnO-qJaRqwRHQkVMJ8CDohWjU8u2JT3CJpU",
    "docs/TDD.md": "1Bpj41LTlT4MKyLSyxtSOvEtdj2kMHsPBSqL6lqeF_nQ",
    "docs/finops-billing-and-deployment-guide.md": "1k8oXmGze3dxOotTvahVEOhQT5qET425wRbmH3mU6miQ",
    "docs/FDE_CAPSTONE_COMPANION_GUIDE.md": "1a_3TPfgm7U2O5S_f4QR_Aey3ptGnICFdAgvzfF-uXYw",
    "docs/CAPSTONE_CONVERSATIONAL_PRESENTATION_AND_DEMO_SCRIPT.md": "11cIHKTVLnIlwRcFcVkC4OR1lCnc40bIYr3aOJvXMGvc",
    "docs/CAPSTONE_ARTIFACT_ANALYZER_REPORT.md": "1xTVDg0mWaK8oUhPiVrEjsA0vcOkZj9CKARse0iNFi7M",
    "docs/CAPSTONE_PANEL_PLAYBOOK.md": "1S80Sja2XTpyHxrSwuaATYaEePbF1PV6CkrCiDbEbiaU",
    "docs/CAPSTONE_SUBMISSION_AND_BUNDLING_GUIDE.md": "13OQXD6ec260-3bLVRwC2hSiSpLJAURT7vkUVW2DeQF4",
}


def _clean_mermaid_label(raw_label: str) -> list[str]:
  """Convert a Mermaid node or edge label into clean wrapped lines."""
  text = raw_label.strip()
  if (text.startswith('"') and text.endswith('"')) or (
      text.startswith("'") and text.endswith("'")
  ):
    text = text[1:-1]
  # Replace literal \n and <br/> variants with newline
  text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
  text = text.replace("\\n", "\n")
  lines: list[str] = []
  for part in text.split("\n"):
    cleaned = part.strip()
    if cleaned:
      lines.append(cleaned)
  return lines or [text]


def parse_mermaid_flowchart(
    mermaid_src: str,
) -> tuple[str, dict[str, dict[str, object]], list[dict[str, str]]]:
  """Parse a Mermaid flowchart (LR or TD) into direction, nodes, and edges."""
  direction = "LR"
  nodes: dict[str, dict[str, object]] = {}
  edges: list[dict[str, str]] = []

  def _register_node_token(token: str) -> str:
    token = token.strip()
    # Match ID["Label"] or ID{"Label"} or ID("Label")
    m_box = re.match(r'^([A-Za-z0-9_]+)\s*\[(.*)\]$', token, re.DOTALL)
    if m_box:
      nid, raw_lbl = m_box.group(1), m_box.group(2)
      nodes[nid] = {"id": nid, "lines": _clean_mermaid_label(raw_lbl), "shape": "box"}
      return nid
    m_diamond = re.match(r'^([A-Za-z0-9_]+)\s*\{(.*)\}$', token, re.DOTALL)
    if m_diamond:
      nid, raw_lbl = m_diamond.group(1), m_diamond.group(2)
      nodes[nid] = {
          "id": nid,
          "lines": _clean_mermaid_label(raw_lbl),
          "shape": "decision",
      }
      return nid
    m_plain = re.match(r'^([A-Za-z0-9_]+)$', token)
    if m_plain:
      nid = m_plain.group(1)
      if nid not in nodes:
        nodes[nid] = {"id": nid, "lines": [nid], "shape": "box"}
      return nid
    return token

  for raw_line in mermaid_src.splitlines():
    line = raw_line.strip()
    if not line or line.startswith("%%"):
      continue
    m_dir = re.match(r"^(?:flowchart|graph)\s+(LR|RL|TD|TB|BT)\b", line, re.I)
    if m_dir:
      d = m_dir.group(1).upper()
      direction = "TB" if d in ("TD", "TB") else "LR"
      continue

    # Match edge patterns:
    # 1) LHS -- "label" --> RHS
    m_edge_lbl1 = re.match(
        r'^(.*?)\s+--\s+"([^"]+)"\s+-->\s+(.*)$', line
    )
    # 2) LHS -.->|"label"| RHS or LHS -->|"label"| RHS
    m_edge_lbl2 = re.match(
        r'^(.*?)\s+(<?[-.=]+>)\|([^|]+)\|\s*(.*)$', line
    )
    # 3) LHS <--> RHS, LHS -.-> RHS, LHS --> RHS
    m_edge_plain = re.match(r'^(.*?)\s+(<-->|-\.->|-->|==>)\s+(.*)$', line)

    if m_edge_lbl1:
      lhs, elabel, rhs = (
          m_edge_lbl1.group(1),
          m_edge_lbl1.group(2),
          m_edge_lbl1.group(3),
      )
      u = _register_node_token(lhs)
      v = _register_node_token(rhs)
      edges.append({"u": u, "v": v, "style": "solid", "dir": "forward", "label": elabel})
    elif m_edge_lbl2:
      lhs, arrow, elabel, rhs = (
          m_edge_lbl2.group(1),
          m_edge_lbl2.group(2),
          m_edge_lbl2.group(3).strip().strip('"'),
          m_edge_lbl2.group(4),
      )
      u = _register_node_token(lhs)
      v = _register_node_token(rhs)
      style = "dashed" if "." in arrow else "solid"
      ed = "both" if arrow.startswith("<") else "forward"
      edges.append({"u": u, "v": v, "style": style, "dir": ed, "label": elabel})
    elif m_edge_plain:
      lhs, arrow, rhs = (
          m_edge_plain.group(1),
          m_edge_plain.group(2),
          m_edge_plain.group(3),
      )
      u = _register_node_token(lhs)
      v = _register_node_token(rhs)
      style = "dashed" if "." in arrow else "solid"
      ed = "both" if arrow.startswith("<") else "forward"
      edges.append({"u": u, "v": v, "style": style, "dir": ed, "label": ""})
    else:
      _register_node_token(line)

  return direction, nodes, edges


def build_graphviz_dot(
    direction: str,
    nodes: dict[str, dict[str, object]],
    edges: list[dict[str, str]],
) -> str:
  """Build a styled Graphviz DOT specification with Scout Navy/Gold palette."""
  # If an LR diagram has more than 5 nodes, arrange it in a clean 2-row snake or TB
  # so that every box text is large and legible inside a portrait Google Doc.
  node_ids = list(nodes.keys())
  use_vertical_flow = direction == "LR" and len(node_ids) >= 6

  rankdir = "LR" if (direction == "LR" and not use_vertical_flow) else "TB"

  dot_lines = [
      "digraph MermaidDiagram {",
      f'  rankdir={rankdir};',
      '  bgcolor="#F8FAFC";',
      '  pad="0.28";',
      '  nodesep="0.40";',
      '  ranksep="0.45";',
      '  splines=spline;',
      '  fontname="Inter, Segoe UI, Roboto, Helvetica, Arial, Noto Color Emoji, sans-serif";',
      '  node [fontname="Inter, Segoe UI, Roboto, Helvetica, Arial, Noto Color Emoji, sans-serif", fontsize=13, penwidth=2.0, margin="0.22,0.14"];',
      '  edge [fontname="Inter, Segoe UI, Roboto, Helvetica, Arial, Noto Color Emoji, sans-serif", fontsize=11, penwidth=2.0, color="#1E3A8A", arrowsize=0.85];',
  ]

  for idx, (nid, info) in enumerate(nodes.items()):
    lines = info["lines"]
    shape = info["shape"]
    escaped_lines: list[str] = []
    for line_idx, l in enumerate(lines):
      esc = html.escape(str(l))
      if line_idx == 0:
        escaped_lines.append(f'<B><FONT POINT-SIZE="13.5">{esc}</FONT></B>')
      else:
        escaped_lines.append(
            f'<FONT POINT-SIZE="11.5" COLOR="#334155">{esc}</FONT>'
        )
    html_label = "<" + "<BR ALIGN=\"CENTER\"/>".join(escaped_lines) + ">"

    if shape == "decision":
      dot_lines.append(
          f'  "{nid}" [label={html_label}, shape=box, style="rounded,filled,dashed",'
          ' fillcolor="#FEF3C7", color="#D97706", fontcolor="#78350F"];'
      )
    elif idx == 0:
      dot_lines.append(
          f'  "{nid}" [label={html_label}, shape=box, style="rounded,filled",'
          ' fillcolor="#EFF6FF", color="#003F87", fontcolor="#0F172A"];'
      )
    elif idx == len(nodes) - 1:
      dot_lines.append(
          f'  "{nid}" [label={html_label}, shape=box, style="rounded,filled",'
          ' fillcolor="#ECFDF5", color="#059669", fontcolor="#064E3B"];'
      )
    else:
      dot_lines.append(
          f'  "{nid}" [label={html_label}, shape=box, style="rounded,filled",'
          ' fillcolor="#FFFFFF", color="#1E3A8A", fontcolor="#0F172A"];'
      )

  for e in edges:
    attrs: list[str] = []
    if e["style"] == "dashed":
      attrs.append('style="dashed"')
      attrs.append('color="#D97706"')
    if e["dir"] == "both":
      attrs.append('dir="both"')
    if e["label"]:
      esc_lbl = html.escape(e["label"])
      attrs.append(
          f'label=<<B><FONT POINT-SIZE="10.5" COLOR="#1E293B"> {esc_lbl} </FONT></B>>'
      )
    attr_str = f" [{', '.join(attrs)}]" if attrs else ""
    dot_lines.append(f'  "{e["u"]}" -> "{e["v"]}"{attr_str};')

  dot_lines.append("}")
  return "\n".join(dot_lines)


def render_mermaid_to_png(mermaid_src: str, out_png: Path) -> None:
  """Render a Mermaid flowchart string to a tightly cropped 2x PNG via dot + Chrome."""
  direction, nodes, edges = parse_mermaid_flowchart(mermaid_src)
  dot_src = build_graphviz_dot(direction, nodes, edges)

  res = subprocess.run(
      ["dot", "-Tsvg"],
      input=dot_src,
      capture_output=True,
      text=True,
      check=True,
  )
  svg_content = res.stdout

  # Extract natural width/height from SVG or wrap in clean HTML container
  html_doc = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    margin: 0;
    padding: 24px;
    background: #FFFFFF;
    display: inline-block;
    font-family: 'Inter', 'Segoe UI', 'Roboto', 'Noto Color Emoji', sans-serif;
  }}
  .diagram-card {{
    display: inline-block;
    background: #F8FAFC;
    border: 2px solid #CBD5E1;
    border-radius: 14px;
    padding: 16px 20px;
    box-shadow: 0 2px 6px rgba(15, 23, 42, 0.06);
  }}
  svg {{
    display: block;
    max-width: 100%;
    height: auto;
  }}
</style>
</head>
<body>
  <div class="diagram-card">
    {svg_content}
  </div>
</body>
</html>
"""
  out_png.parent.mkdir(parents=True, exist_ok=True)
  with tempfile.TemporaryDirectory() as tmpdir:
    html_path = Path(tmpdir) / "diagram.html"
    raw_png = Path(tmpdir) / "raw.png"
    html_path.write_text(html_doc, encoding="utf-8")

    subprocess.run(
        [
            CHROME_BIN,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-device-scale-factor=2",
            "--window-size=2000,1600",
            f"--screenshot={raw_png}",
            f"file://{html_path}",
        ],
        check=True,
        capture_output=True,
    )

    # Crop whitespace tightly around the diagram card with a clean 12px white margin
    img = Image.open(raw_png).convert("RGB")
    bg = Image.new("RGB", img.size, (255, 255, 255))
    diff = ImageChops.difference(img, bg)
    bbox = diff.getbbox()
    if bbox:
      pad = 16
      left = max(0, bbox[0] - pad)
      top = max(0, bbox[1] - pad)
      right = min(img.width, bbox[2] + pad)
      bottom = min(img.height, bbox[3] + pad)
      img = img.crop((left, top, right, bottom))
    if img.width > 1800:
      new_h = max(1, int(round(img.height * (1800 / img.width))))
      img = img.resize((1800, new_h), Image.Resampling.LANCZOS)
    img.save(out_png, format="PNG", optimize=True)


def _doc_has_conversion_errors(doc_id: str) -> bool:
  """Check via Drive API text export (0 Docs API quota) whether any image failed."""
  with tempfile.TemporaryDirectory() as tmpdir:
    out_txt = Path(tmpdir) / "doc.txt"
    res = subprocess.run(
        [GDOCS_BIN, "readonly", "export", doc_id, "--format", "txt", "-o", str(out_txt)],
        capture_output=True,
        text=True,
    )
    if res.returncode == 0 and out_txt.exists():
      txt = out_txt.read_text(encoding="utf-8", errors="ignore")
      if "image conversion failed" in txt.lower() or "```mermaid" in txt.lower():
        return True
  return False


def process_markdown_file(
    md_rel_path: str, sync_gdoc: bool = False
) -> list[Path]:
  """Render all Mermaid blocks in md_rel_path and optionally sync to Google Docs."""
  md_path = REPO_ROOT / md_rel_path
  if not md_path.exists():
    raise FileNotFoundError(f"Markdown file not found: {md_path}")

  text = md_path.read_text(encoding="utf-8")
  slug = md_path.stem.lower().replace("_", "-")
  pattern = re.compile(r"```mermaid\n(.*?)```", re.DOTALL)
  matches = list(pattern.finditer(text))

  rendered_pngs: list[Path] = []
  for idx, m in enumerate(matches, 1):
    png_name = f"mermaid-{slug}-{idx}.png"
    out_png = IMAGES_DIR / png_name
    render_mermaid_to_png(m.group(1), out_png)
    rendered_pngs.append(out_png)
    print(f"[MERMAID-PNG] Rendered {md_rel_path} block #{idx} -> docs/images/{png_name}")

  if sync_gdoc and md_rel_path in COMPANION_GDOCS:
    doc_id = COMPANION_GDOCS[md_rel_path]
    # Build temporary markdown in the same directory so relative image paths resolve
    counter = 0

    def _repl(match: re.Match[str]) -> str:
      nonlocal counter
      counter += 1
      png_name = f"mermaid-{slug}-{counter}.png"
      rel_img_path = (
          f"images/{png_name}"
          if md_path.parent == (REPO_ROOT / "docs")
          else f"docs/images/{png_name}"
      )
      return f"![Architecture and Workflow Diagram {counter}]({rel_img_path})"

    synced_md_text = pattern.sub(_repl, text)
    temp_md_path = md_path.parent / f".{md_path.stem}.gdoc-sync.md"
    try:
      temp_md_path.write_text(synced_md_text, encoding="utf-8")
      for attempt in range(1, 4):
        print(
            f"[GDOCS-SYNC] Updating Google Doc {doc_id} from {md_rel_path} (attempt {attempt})..."
        )
        cmd = [
            GDOCS_BIN,
            "mutate",
            "import-md",
            str(temp_md_path),
            "--update",
            doc_id,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        combined_out = (res.stdout or "") + "\n" + (res.stderr or "")
        has_err = (
            res.returncode != 0
            or "image conversion failed" in combined_out.lower()
            or "error 429" in combined_out.lower()
            or _doc_has_conversion_errors(doc_id)
        )
        if not has_err:
          print(
              f"[GDOCS-OK] Verified 0 image conversion errors in {md_rel_path} ->"
              f" https://docs.google.com/document/d/{doc_id}/edit"
          )
          break
        print(
            f"[GDOCS-RETRY] Detected transient 429 quota during image import for {md_rel_path};"
            " sleeping 35s before retry..."
        )
        time.sleep(35)
    finally:
      if temp_md_path.exists():
        temp_md_path.unlink()

  return rendered_pngs


def main() -> None:
  parser = argparse.ArgumentParser(
      description="Render Markdown Mermaid diagrams to PNGs and sync to Google Docs."
  )
  parser.add_argument(
      "--render-only",
      action="store_true",
      help="Only render Mermaid diagrams to docs/images/mermaid-*.png without calling gdocs.",
  )
  parser.add_argument(
      "--sync-gdocs",
      action="store_true",
      help="Render Mermaid diagrams and sync companion Google Docs.",
  )
  parser.add_argument(
      "--only",
      nargs="*",
      help="Optional list of relative .md paths (e.g. docs/USER_GUIDE.md docs/ADMIN_GUIDE.md).",
  )
  args = parser.parse_args()

  target_files = args.only or [
      "README.md",
      "docs/USER_GUIDE.md",
      "docs/ADMIN_GUIDE.md",
      "docs/TDD.md",
      "docs/finops-billing-and-deployment-guide.md",
  ]

  for i, rel_path in enumerate(target_files):
    process_markdown_file(rel_path, sync_gdoc=args.sync_gdocs and not args.render_only)
    if args.sync_gdocs and not args.render_only and i < len(target_files) - 1:
      time.sleep(2)


if __name__ == "__main__":
  main()
