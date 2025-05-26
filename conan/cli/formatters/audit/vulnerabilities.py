import json

from jinja2 import select_autoescape, Template

from conan.api.output import cli_out_write, Color
from conan.errors import ConanException

severity_order = {
    "Critical": 4,
    "High": 3,
    "Medium": 2,
    "Low": 1
}


def text_vuln_formatter(result):

    severity_colors = {
        "Critical": Color.BRIGHT_RED,
        "High": Color.RED,
        "Medium": Color.BRIGHT_YELLOW,
        "Low": Color.BRIGHT_CYAN
    }

    def wrap_and_indent(txt, limit=80, indent=2):
        txt = txt.replace("\n", " ").strip()
        if len(txt) <= limit:
            return " " * indent + txt
        lines = []
        while len(txt) > limit:
            split_index = txt.rfind(" ", 0, limit)
            if split_index == -1:
                split_index = limit
            lines.append(" " * indent + txt[:split_index].strip())
            txt = txt[split_index:].strip()
        lines.append(" " * indent + txt)
        return "\n".join(lines)

    total_vulns = 0
    summary_lines = []

    for ref, pkg_info in result["data"].items():
        edges = pkg_info.get("vulnerabilities", {}).get("edges", [])
        count = len(edges)

        border_line = "*" * (len(ref) + 4)
        cli_out_write("\n" + border_line, fg=Color.BRIGHT_WHITE)
        cli_out_write(f"* {ref} *", fg=Color.BRIGHT_WHITE)
        cli_out_write(border_line, fg=Color.BRIGHT_WHITE)

        if "error" in pkg_info:
            details = pkg_info["error"].get("details", "")
            cli_out_write(f"\n{details}\n", fg=Color.BRIGHT_YELLOW)
            continue

        if not count:
            cli_out_write("\nNo vulnerabilities found.\n", fg=Color.BRIGHT_GREEN)
            continue

        total_vulns += count
        summary_lines.append(
            f"{ref} {count} {'vulnerability' if count == 1 else 'vulnerabilities'} found")
        cli_out_write(f"\n{count} {'vulnerability' if count == 1 else 'vulnerabilities'} found:\n",
                      fg=Color.BRIGHT_YELLOW)

        sorted_vulns = sorted(edges,
                              key=lambda v: -severity_order.get(v["node"].get("severity", "Medium"),
                                                                2))

        for vuln in sorted_vulns:
            node = vuln["node"]
            name = node["name"]
            sev = node.get("severity", "Medium")
            sev_color = severity_colors.get(sev, Color.BRIGHT_YELLOW)
            score = node.get("cvss", {}).get("preferredBaseScore")
            score_txt = f", CVSS: {score}" if score else ""
            desc = node.get("description", "")
            desc = (desc[:240] + "...") if len(desc) > 240 else desc
            desc_wrapped = wrap_and_indent(desc)

            cli_out_write(f"- {name}", fg=Color.BRIGHT_WHITE, endline="")
            cli_out_write(f" (Severity: {sev}{score_txt})", fg=sev_color)
            cli_out_write("\n" + desc_wrapped)

            references = node.get("references")
            if references:
                cli_out_write(f"  url: {references[0]}", fg=Color.BRIGHT_BLUE)
            cli_out_write("")

    color_for_total = Color.BRIGHT_RED if total_vulns else Color.BRIGHT_GREEN

    cli_out_write(f"Total vulnerabilities found: {total_vulns}\n", fg=color_for_total)

    if total_vulns > 0:
        cli_out_write("\nSummary:\n", fg=Color.BRIGHT_WHITE)
        for line in summary_lines:
            cli_out_write(f"- {line}", fg=Color.BRIGHT_WHITE)

        cli_out_write("\nIf you are using packages from Conan Center, some vulnerabilities may have already been mitigated "
                      "through patches applied in the recipe.\nTo verify if a patch has been applied, check the recipe in Conan Center.\n",
                      fg=Color.BRIGHT_YELLOW)

    if total_vulns > 0 or not "error" in result:
        cli_out_write("\nVulnerability information provided by JFrog Catalog. Check "
                      "https://audit.conan.io/jfrogcuration for more information.\n",
                      fg=Color.BRIGHT_GREEN)
        cli_out_write("You can send questions and report issues about "
                      "the returned vulnerabilities to conan-research@jfrog.com.\n",
                      fg=Color.BRIGHT_GREEN)


def json_vuln_formatter(result):
    cli_out_write(json.dumps(result, indent=4))


def _render_vulns(vulns, template):
    from conan import __version__
    template = Template(template, autoescape=select_autoescape(['html', 'xml']))
    return template.render(vulns=vulns, version=__version__)

vuln_html = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <title>Conan Audit Vulnerabilities Report</title>
  <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">
  <style>
    body { margin: 0; padding: 0; font-family: Arial, sans-serif; background: #333; color: #ffffff; }
    .container { width: 80%; margin: 40px auto; padding: 20px; background: #222; box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-radius: 8px; }
    h1 { text-align: center; margin-bottom: 20px; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 20px; table-layout: fixed; padding-top: 10px;}
    col.pkg-col   { width: 15%; }
    col.id-col    { width: 15%; }
    col.sev-col   { width: 15%; }
    col.score-col { width: 15%; }
    col.desc-col  { width: 40%; }
    thead { background: #333; color: #fff; }
    thead th { padding: 12px; text-align: left; }
    tbody tr { border-bottom: 1px solid #ddd; }
    tbody tr:hover { background: #f0f0f0; }
    td { padding: 10px; vertical-align: top; white-space: normal; word-wrap: break-word; overflow-wrap: break-word; word-break: break-word;}
    .severity-badge { padding: 4px 8px; border-radius: 4px; color: #fff; font-weight: bold; display: inline-block; }
    .severity-Critical { background: #d9534f; animation: pulse 2s infinite; }
    @keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(217,83,79,0.7); } 70% { box-shadow: 0 0 0 12px rgba(217,83,79,0); } 100% { box-shadow: 0 0 0 0 rgba(217,83,79,0); } }
    .severity-High { background: #f0ad4e; }
    .severity-Medium { background: #f7ecb5; color: #333; }
    .severity-Low { background: #5cb85c; }
    .footer { text-align: center; color: #666; margin-bottom: 10px; }
    a { color: #007bff; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
  <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
  <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>
  <script>
    $(document).ready(function(){
      $('#vuln_table').DataTable({
        "columnDefs": [
          { "orderable": true, "targets": [0, 1, 2] },
          { "orderable": false, "targets": [3, 4] }
        ],
        "order": [[2, "desc"]],
      });
    });
  </script>
</head>
<body>
  <div class="container">
    <h1>Conan Audit Vulnerabilities Report</h1>
    <table id="vuln_table">
      <colgroup>
        <col class="pkg-col">
        <col class="id-col">
        <col class="sev-col">
        <col class="score-col">
        <col class="desc-col">
      </colgroup>
      <thead>
        <tr>
          <th>Package</th>
          <th>ID</th>
          <th>Severity</th>
          <th>Score</th>
          <th>Description</th>
        </tr>
      </thead>
      <tbody>
      {% for vuln in vulns %}
        {% set parts = vuln.severity.split(' - ') %}
        {% set severity_id = parts[0] %}
        {% set severity_label = parts[1] if parts|length > 1 else parts[0] %}
        <tr>
          <td>{{ vuln.package }}</td>
          <td>{{ vuln.vuln_id }}</td>
          <td>
            <span style="display: none">{% if severity_id == 'N/A' %}-1{% else %}{{ severity_id }}{% endif %}</span>
            {% if vuln.severity not in ['N/A', ''] %}
              <span class="severity-badge severity-{{ severity_label }}">{{ severity_label }}</span>
            {% else %}
              {{ vuln.severity }}
            {% endif %}
          </td>
          <td>{{ vuln.score }}</td>
          <td>
            {{ vuln.description }}
            {% if vuln.references %}
              <br><br><strong>References:</strong>
              <ul>
                {% for ref in vuln.references %}
                  <li><a href="{{ ref }}" target="_blank">{{ ref }}</a></li>
                {% endfor %}
              </ul>
            {% endif %}
            {% if vuln.aliases %}
              <br><br><strong>Aliases:</strong> {{ ', '.join(vuln.aliases) }}
            {% endif %}
          </td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
    <div class="footer">
      <p>Vulnerability information provided by JFrog Advanced Security. Please check <a href="https://jfrog.com/advanced-security/" target="_blank">https://jfrog.com/advanced-security/</a> for more information.</p>
      <p>You can send questions and report issues about the returned vulnerabilities to <a href="mailto:conan-research@jfrog.com">conan-research@jfrog.com</a>.</p>
      <p>Conan version: {{ version }}</p>
    </div>
  </div>
</body>
</html>
"""

def html_vuln_formatter(result):
    vulns = []
    for ref, pkg_info in result["data"].items():
        edges = pkg_info.get("vulnerabilities", {}).get("edges", [])
        if not edges:
            description = "No vulnerabilities found." if not "error" in pkg_info else pkg_info["error"].get("details", "")
            vulns.append({
                "package": ref,
                "vuln_id": "-",
                "aliases": [],
                "severity": "N/A",
                "score": "-",
                "description": description,
                "references": []
            })
        else:
            sorted_vulns = sorted(edges, key=lambda v: -severity_order.get(v["node"].get("severity", "Medium"), 2))
            for vuln in sorted_vulns:
                node = vuln["node"]
                name = node.get("name")
                sev = node.get("severity", "Medium")
                sev = f"{severity_order.get(sev, 2)} - {sev}"
                score = node.get("cvss", {}).get("preferredBaseScore")
                score_txt = f"CVSS: {score}" if score else "-"
                aliases = node.get("aliases", [])
                references = node.get("references", [])
                desc = node.get("description", "")
                vulns.append({
                    "package": ref,
                    "vuln_id": name,
                    "aliases": aliases,
                    "severity": sev,
                    "score": score_txt,
                    "description": desc,
                    "references": references,
                })

    cli_out_write(_render_vulns(vulns, vuln_html))
