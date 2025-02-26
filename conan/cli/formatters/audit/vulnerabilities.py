import json

from jinja2 import select_autoescape, Template

from conan.api.output import cli_out_write, Color, ConanOutput

severity_order = {
    "Critical": 4,
    "High": 3,
    "Medium": 2,
    "Low": 1
}

def text_vuln_formatter(result):
    from conan.api.output import cli_out_write, Color

    data_json, errors_in_response = result

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

    if not data_json or "data" not in data_json or not data_json["data"]:
        if not errors_in_response:
            cli_out_write("No vulnerabilities found.\n", fg=Color.BRIGHT_GREEN)
        return

    total_vulns = 0
    summary_lines = []

    for pkg_name, pkg_info in data_json["data"].items():
        ref = f"{pkg_name}/{pkg_info['version']}"
        edges = pkg_info.get("vulnerabilities", {}).get("edges", [])
        count = len(edges)

        border_line = "*" * (len(ref) + 4)
        cli_out_write("\n" + border_line, fg=Color.BRIGHT_WHITE)
        cli_out_write(f"* {ref} *", fg=Color.BRIGHT_WHITE)
        cli_out_write(border_line, fg=Color.BRIGHT_WHITE)

        if not count:
            if not errors_in_response:
                cli_out_write("\nNo vulnerabilities found.\n", fg=Color.BRIGHT_GREEN)
                continue

        total_vulns += count
        summary_lines.append(f"{ref} {count} {'vulnerability' if count == 1 else 'vulnerabilities'} found")
        cli_out_write(f"\n{count} {'vulnerability' if count == 1 else 'vulnerabilities'} found:\n", fg=Color.BRIGHT_YELLOW)

        sorted_vulns = sorted(edges, key=lambda v: -severity_order.get(v["node"].get("severity", "Medium"), 2))

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

    cli_out_write("\nSummary:\n", fg=Color.BRIGHT_WHITE)
    for line in summary_lines:
        cli_out_write(f"- {line}", fg=Color.BRIGHT_WHITE)

    cli_out_write("\nVulnerability information provided by JFrog. Please check "
                  "https://jfrog.com/advanced-security/ for more information.\n", fg=Color.BRIGHT_GREEN)
    cli_out_write("You can send questions and report issues about "
                  "the returned vulnerabilities to conan-research@jfrog.com.\n", fg=Color.BRIGHT_GREEN)

def json_vuln_formatter(result):
    data, errors_in_response = result
    cli_out_write(json.dumps(data, indent=4))


def _render_vulns(vulns, template):
    from conan import __version__
    template = Template(template, autoescape=select_autoescape(['html', 'xml']))
    return template.render(vulns=vulns, version=__version__)

vuln_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <title>Audited Vulnerabilities</title>

    <script src="https://code.jquery.com/jquery-3.7.1.slim.min.js"
    integrity="sha256-kmHvs0B+OpCW5GVHUNjv9rOmY0IvSIRcf7zGUDTDQM8="
    crossorigin="anonymous"></script>

    <link rel="stylesheet" href="https://cdn.datatables.net/2.2.2/css/dataTables.dataTables.css" />
    <script src="https://cdn.datatables.net/2.2.2/js/dataTables.js"></script>

    <script>
        $(document).ready(function() {
            const table = new DataTable('#vuln_table', {
                // Order by severity descending, then by package name ascending
                order: [[2, 'desc'], [0, 'asc']],
            });
        });
    </script>
</head>
<body>
    <table id="vuln_table" class="stripe" style="width:100%">
        <thead>
            <tr>
            <th>Package</th>
            <th>Vulnerability ID</th>
            <th>Severity</th>
            <th>Score</th>
            <th>Description</th>
            </tr>
        </thead>
        <tbody>
        {% for vuln in vulns %}
            <tr>
                <td>{{ vuln.package }}</td>
                <td>{{ vuln.vuln_id }}</td>
                <td>{{ vuln.severity }}</td>
                <td>{{ vuln.score }}</td>
                <td>{{ vuln.description }}</td>
            </tr>
        {% endfor %}
        </tbody>
    </table>
    <a href="https://jfrog.com/advanced-security/">Vulnerability information provided by JFrog</a>
</body>
</html>
"""

def html_vuln_formatter(result):
    data_json, errors_in_response = result
    vulns = []
    for pkg_name, pkg_info in data_json["data"].items():
        ref = f"{pkg_name}/{pkg_info['version']}"
        edges = pkg_info.get("vulnerabilities", {}).get("edges", [])
        count = len(edges)
        if not count:
            continue

        sorted_vulns = sorted(edges,
                              key=lambda v: -severity_order.get(v["node"].get("severity", "Medium"),
                                                                2))

        for vuln in sorted_vulns:
            node = vuln["node"]
            name = node["name"]
            sev = node.get("severity", "Medium")
            sev = f"{severity_order.get(sev, 2)} - {sev}"
            score = node.get("cvss", {}).get("preferredBaseScore")
            score_txt = f", CVSS: {score}" if score else "-"
            desc = node.get("description", "")

            # TODO: Show these?
            references = node.get("references")
            vulns.append({
                "package": ref,
                "vuln_id": name,
                "severity": sev,
                "score": score_txt,
                "description": desc,
            })
    cli_out_write(_render_vulns(vulns, vuln_html))
