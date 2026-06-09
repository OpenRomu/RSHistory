#!/usr/bin/env python3
import argparse
import html
import sys

try:
    import yaml
except ImportError:
    sys.exit("Install pyyaml")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{ font-family: system-ui, sans-serif; }}
  body {{ margin: 2rem auto; max-width: 1100px; padding: 0 1rem; color: #1a1a1a; }}
  h1 {{ margin-bottom: .2rem; }}
  .meta {{ color: #555; margin-bottom: 1.5rem; }}
  table {{ border-collapse: collapse; width: 100%; font-size: .95rem; }}
  th, td {{ border: 1px solid #ccc; padding: .45rem .6rem; text-align: left; vertical-align: top; }}
  th {{ background: #2b2b2b; color: #fff; position: sticky; top: 0; }}
  tr.summary {{ cursor: default; }}
  /* Legend colors, good enough */
  .row-green  {{ background: #d6f5d6; }}
  .row-yellow {{ background: #f6f6c2; }}
  .row-orange {{ background: #ffe0b3; }}
  .row-red    {{ background: #f9c9c9; }}
  .row-gray   {{ background: #e2e2e2; }}
  .detail-row > td {{ background: #fafafa; }}
  .detail-row {{ display: none; }}
  .detail-row.open {{ display: table-row; }}
  .toggle {{ cursor: pointer; color: #0b5cad; font-weight: bold; user-select: none; }}
  .toggle:hover {{ text-decoration: underline; }}
  dl {{ margin: 0; }}
  dt {{ font-weight: bold; margin-top: .4rem; }}
  dd {{ margin: 0 0 .2rem 1rem; }}
  pre {{ background: #f0f0f0; padding: .5rem; border-radius: 4px; white-space: pre-wrap; }}
  code {{ word-break: break-all; }}
  .legend {{ margin: 1rem 0 1.5rem; display: flex; flex-wrap: wrap; gap: .6rem; }}
  .legend span {{ padding: .25rem .6rem; border: 1px solid #aaa; border-radius: 4px; font-size: .85rem; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="meta">{description}{creator}{predecessors}</div>

<div class="legend">
  <span class="row-green">Confirmed &amp; Preserved</span>
  <span class="row-yellow">Confirmed &amp; Partial</span>
  <span class="row-orange">Confirmed &amp; Lost</span>
  <span class="row-red">Inferred</span>
  <span class="row-gray">Unconfirmed</span>
</div>

<table>
  <thead>
    <tr>
      <th>Version</th><th>Date</th><th>Version certainty</th>
      <th>Date certainty</th><th>Archive status</th><th>Creator</th>
      <th>Download</th><th>Details</th>
    </tr>
  </thead>
  <tbody>
{rows}
  </tbody>
</table>

<script>
function toggleDetails(id) {{
  var row = document.getElementById(id);
  if (row) row.classList.toggle('open');
}}
</script>
</body>
</html>
"""

def get_creator(version: dict, project: dict) -> list:
    """Per-version creator overrides the project-level creator if needed"""
    if version.get("creator"):
        return version["creator"]
    return project.get("creator", [])

def row_color(version: dict) -> tuple[str, str]:
    """
    Return (css_class, human_label) according to the legend
      Green  : confirmed AND preserved
      Yellow : confirmed AND partial
      Orange: confirmed AND lost
      Red : inferred
      Gray : unconfirmed
    """
    vc = (version.get("version_certainty") or "").lower()
    arch = (version.get("archive_status") or "").lower()

    if vc == "unconfirmed":
        return "row-gray", "Unconfirmed"
    if vc == "inferred":
        return "row-red", "Inferred"
    if vc == "confirmed":
        if arch == "preserved":
            return "row-green", "Confirmed - Preserved"
        if arch == "partial":
            return "row-yellow", "Confirmed - Partial"
        if arch == "lost":
            return "row-orange", "Confirmed - Lost"
        return "row-gray", "Confirmed - Unknown archive"
    # Missing / bogus thingy 
    return "row-gray", "Unknown"

def fmt_creator(creators: list) -> str:
    return ", ".join(creators) if creators else "-"

def fmt_size(size_kb) -> str:
    if size_kb in (None, "", "~"):
        return "(unknown)"
    try:
        kb = float(size_kb)
    except (TypeError, ValueError):
        return str(size_kb)
    if kb >= 1024:
        return f"{kb/1024:.1f} MB ({int(kb)} KB)"
    return f"{int(kb)} KB"

def archive_dl_summary(version: dict, *, as_html: bool) -> str:
    """Short representation of archive_download for the main table"""
    dl = version.get("archive_download")
    if not dl:
        return "-"
    url = dl.get("url", "")
    fname = dl.get("filename") or "download"
    dtype = dl.get("type", "")
    label = fname + (f" ({dtype})" if dtype else "")
    if not url:
        return html.escape(label) if as_html else label
    if as_html:
        return f'<a href="{html.escape(url)}">{html.escape(label)}</a>'
    return f"[{label}]({url})"

def md_escape(text) -> str:
    if text is None:
        return ""
    return str(text).replace("|", "\\|").replace("\n", " ")

def build_markdown(data: dict) -> str:
    project = data.get("project", {})
    versions = data.get("versions", [])

    out = []
    out.append(f"# {project.get('name', 'Project')} - Version History\n")
    if project.get("description"):
        out.append(f"_{project['description']}_\n")
    if project.get("creator"):
        out.append(f"**Creator(s):** {fmt_creator(project['creator'])}\n")
    if project.get("predecessors"):
        out.append(f"**Predecessor(s):** {', '.join(project['predecessors'])}\n")

    # Recap table
    out.append("\n## Recap\n")
    headers = ["Version", "Date", "Version certainty", "Date certainty",
               "Archive status", "Creator", "Download", "Status"]
    out.append("| " + " | ".join(headers) + " |")
    out.append("|" + "|".join(["---"] * len(headers)) + "|")

    for v in versions:
        _, label = row_color(v)
        cells = [
            md_escape(v.get("version", "?")),
            md_escape(v.get("date", "?")),
            md_escape(v.get("version_certainty", "-")),
            md_escape(v.get("date_certainty", "-")),
            md_escape(v.get("archive_status", "-")),
            md_escape(fmt_creator(get_creator(v, project))),
            archive_dl_summary(v, as_html=False),
            md_escape(label),
        ]
        out.append("| " + " | ".join(cells) + " |")

    # Detail sections
    out.append("\n## Details\n")
    for v in versions:
        out.append(f"### Version {v.get('version', '?')} ({v.get('date', '?')})\n")
        out.extend(md_details(v, project))
        out.append("")

    return "\n".join(out) + "\n"

def md_details(v: dict, project: dict) -> list[str]:
    lines = []

    def kv(key, value):
        if value not in (None, "", [], {}):
            lines.append(f"- **{key}:** {value}")

    kv("Version certainty", v.get("version_certainty"))
    kv("Date certainty", v.get("date_certainty"))
    kv("Archive status", v.get("archive_status"))
    kv("Archive notes", v.get("archive_notes"))
    kv("Creator", fmt_creator(get_creator(v, project)))
    kv("Language", v.get("language"))
    kv("Original filename", v.get("original_filename"))
    kv("Size", fmt_size(v.get("size_kb")))
    kv("Changelog origin", v.get("changelog_origin"))
    kv("Notes", v.get("notes"))
    kv("Obsolete download link", v.get("obsolete_download_link"))

    dl = v.get("archive_download")
    if dl:
        lines.append("- **Archive download:**")
        for k in ("url", "filename", "type"):
            if dl.get(k):
                lines.append(f"    - {k}: {dl[k]}")

    if v.get("changelog"):
        lines.append("- **Changelog:**")
        for cl in str(v["changelog"]).splitlines():
            if cl.strip():
                lines.append(f"    {cl}")

    if v.get("dates_seen"):
        lines.append("- **Dates seen:**")
        for d in v["dates_seen"]:
            lines.append(f"    - {d.get('date', '?')} - {d.get('context', '')}")

    if v.get("hashes"):
        lines.append("- **Hashes:**")
        for algo, val in v["hashes"].items():
            lines.append(f"    - {algo}: `{val}`")

    if v.get("sources"):
        lines.append("- **Sources:**")
        for s in v["sources"]:
            stype = f" _{s['type']}_" if s.get("type") else ""
            if s.get("url"):
                lines.append(f"    - [{s.get('label', s['url'])}]({s['url']}){stype}")
            else:
                lines.append(f"    - {s.get('label', '?')}{stype}")

    return lines

def h(text) -> str:
    return html.escape("" if text is None else str(text))

def build_html(data: dict) -> str:
    project = data.get("project", {})
    versions = data.get("versions", [])

    creator = ""
    if project.get("creator"):
        creator = f" - Default creator: {h(fmt_creator(project['creator']))}"
    predecessors = ""
    if project.get("predecessors"):
        predecessors = f" - Predecessor(s): {h(', '.join(project['predecessors']))}"

    rows = []
    n_cols = 8
    for i, v in enumerate(versions):
        css, _ = row_color(v)
        detail_id = f"detail-{i}"

        # Summary row
        rows.append(f'    <tr class="summary {css}">')
        rows.append(f"      <td>{h(v.get('version', '?'))}</td>")
        rows.append(f"      <td>{h(v.get('date', '?'))}</td>")
        rows.append(f"      <td>{h(v.get('version_certainty', '-'))}</td>")
        rows.append(f"      <td>{h(v.get('date_certainty', '-'))}</td>")
        rows.append(f"      <td>{h(v.get('archive_status', '-'))}</td>")
        rows.append(f"      <td>{h(fmt_creator(get_creator(v, project)))}</td>")
        rows.append(f"      <td>{archive_dl_summary(v, as_html=True)}</td>")
        rows.append(
            f'      <td><span class="toggle" '
            f'onclick="toggleDetails(\'{detail_id}\')">[Details]</span></td>'
        )
        rows.append("    </tr>")

        # Hidden detail row
        rows.append(f'    <tr class="detail-row" id="{detail_id}">')
        rows.append(f'      <td colspan="{n_cols}">')
        rows.append(html_details(v, project))
        rows.append("      </td>")
        rows.append("    </tr>")

    return HTML_TEMPLATE.format(
        title=h(project.get("name", "Project") + " - Version History"),
        description=h(project.get("description", "")),
        creator=creator,
        predecessors=predecessors,
        rows="\n".join(rows),
    )

def html_details(v: dict, project: dict) -> str:
    parts = ["<dl>"]

    def add(label, value):
        if value not in (None, "", [], {}):
            parts.append(f"<dt>{h(label)}</dt><dd>{value}</dd>")

    add("Version certainty", h(v.get("version_certainty")))
    add("Date certainty", h(v.get("date_certainty")))
    add("Archive status", h(v.get("archive_status")))
    add("Archive notes", h(v.get("archive_notes")))
    add("Creator", h(fmt_creator(get_creator(v, project))))
    add("Language", h(v.get("language")))
    add("Original filename", h(v.get("original_filename")))
    add("Size", h(fmt_size(v.get("size_kb"))))
    add("Changelog origin", h(v.get("changelog_origin")))
    add("Notes", h(v.get("notes")))

    dl = v.get("archive_download")
    if dl:
        bits = []
        if dl.get("url"):
            bits.append(f'<a href="{h(dl["url"])}">{h(dl.get("filename") or dl["url"])}</a>')
        elif dl.get("filename"):
            bits.append(h(dl["filename"]))
        if dl.get("type"):
            bits.append(f"({h(dl['type'])})")
        add("Archive download", " ".join(bits))

    if v.get("obsolete_download_link"):
        add("Obsolete download link",
            f"<code>{h(v['obsolete_download_link'])}</code>")

    if v.get("changelog"):
        add("Changelog", f"<pre>{h(v['changelog'])}</pre>")

    if v.get("dates_seen"):
        items = "".join(
            f"<li>{h(d.get('date', '?'))} - {h(d.get('context', ''))}</li>"
            for d in v["dates_seen"]
        )
        add("Dates seen", f"<ul>{items}</ul>")

    if v.get("hashes"):
        items = "".join(
            f"<li>{h(algo)}: <code>{h(val)}</code></li>"
            for algo, val in v["hashes"].items()
        )
        add("Hashes", f"<ul>{items}</ul>")

    if v.get("sources"):
        items = []
        for s in v["sources"]:
            stype = f" <em>({h(s['type'])})</em>" if s.get("type") else ""
            if s.get("url"):
                items.append(
                    f'<li><a href="{h(s["url"])}">'
                    f'{h(s.get("label", s["url"]))}</a>{stype}</li>'
                )
            else:
                items.append(f"<li>{h(s.get('label', '?'))}{stype}</li>")
        add("Sources", f"<ul>{''.join(items)}</ul>")

    parts.append("</dl>")
    return "".join(parts)

def main():
    ap = argparse.ArgumentParser(description="Build HTML + Markdown from a version YAML")
    ap.add_argument("yaml_file", help="Input YAML file")
    ap.add_argument("--html", default="versions.html", help="Output HTML")
    ap.add_argument("--md", default="HISTORY.md", help="Output Markdown")
    args = ap.parse_args()

    with open(args.yaml_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    with open(args.html, "w", encoding="utf-8") as f:
        f.write(build_html(data))
    with open(args.md, "w", encoding="utf-8") as f:
        f.write(build_markdown(data))

    print(f"Wrote {args.html} and {args.md}")

if __name__ == "__main__":
    main()
