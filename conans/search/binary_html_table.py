from collections import namedtuple, defaultdict
from conans.util.files import save


def html_binary_graph(search_info, reference, table_filename):
    result = ["""<style>
    table, th, td {
    border: 1px solid black;
    border-collapse: collapse;
}
.selected {
    border: 3px solid black;
}
</style>
<script type="text/javascript">
    function handleEvent(id) {
        selected = document.getElementsByClassName('selected');
        if (selected[0]) selected[0].className = '';
        cell = document.getElementById(id);
        cell.className = 'selected';
        elem = document.getElementById('SelectedPackage');
        elem.innerHTML = id;
    }

</script>
<h1>%s</h1>
    """ % str(reference)]

    for remote_info in search_info:
        if remote_info["remote"] != 'None':
            result.append("<h2>'%s':</h2>" % str(remote_info["remote"]))

        ordered_packages = remote_info["items"][0]["packages"]
        binary = namedtuple("Binary", "ID outdated")
        columns = set()
        table = defaultdict(dict)
        for package in ordered_packages:
            package_id = package["id"]
            settings = package["settings"]
            if settings:
                row_name = "%s %s %s" % (settings.get("os", "None"),
                                         settings.get("compiler", "None"),
                                         settings.get("compiler.version", "None"))
                column_name = []
                for setting, value in settings.items():
                    if setting.startswith("compiler."):
                        if not setting.startswith("compiler.version"):
                            row_name += " (%s)" % value
                    elif setting not in ("os", "compiler"):
                        column_name.append(value)
                column_name = " ".join(column_name)
            else:
                row_name = "NO settings"
                column_name = ""

            options = package["options"]
            if options:
                for k, v in options.items():
                    column_name += "<br>%s=%s" % (k, v)

            column_name = column_name or "NO options"
            columns.add(column_name)
            # Always compare outdated with local recipe, simplification,
            # if a remote check is needed install recipe first
            if "outdated" in package:
                outdated = package["outdated"]
            else:
                outdated = None
            table[row_name][column_name] = binary(package_id, outdated)

        headers = sorted(columns)
        result.append("<table>")
        result.append("<tr>")
        result.append("<th></th>")
        for header in headers:
            result.append("<th>%s</th>" % header)
        result.append("</tr>")
        for row, columns in sorted(table.items()):
            result.append("<tr>")
            result.append("<td>%s</td>" % row)
            for header in headers:
                col = columns.get(header, "")
                if col:
                    color = "#ffff00" if col.outdated else "#00ff00"
                    result.append('<td bgcolor=%s id="%s" onclick=handleEvent("%s")></td>'
                                  % (color, col.ID, col.ID))
                else:
                    result.append("<td></td>")
            result.append("</tr>")
        result.append("</table>")

    result.append('<br>Selected: <div id="SelectedPackage"></div>')

    result.append("<br>Legend<br>"
                  "<table><tr><td bgcolor=#ffff00>&nbsp;&nbsp;&nbsp;&nbsp;</td"
                  "<td>Outdated from recipe</td></tr>"
                  "<tr><td bgcolor=#00ff00>&nbsp;&nbsp;&nbsp;&nbsp;</td><td>Updated</td></tr>"
                  "<tr><td>&nbsp;&nbsp;&nbsp;&nbsp;</td><td>Non existing</td></tr></table>")
    html_contents = "\n".join(result)
    save(table_filename, html_contents)
