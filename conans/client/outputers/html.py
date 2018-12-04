# coding=utf-8

from collections import defaultdict, namedtuple
from contextlib import contextmanager

from conans.util.files import save
from conans.client.outputers.base_outputer import BaseOutputer
from conans.client.outputers.formats import OutputerFormats


@contextmanager
def html(tag, content):
    content.append("<{}>".format(tag))
    yield content
    content.append("</{}>".format(tag))


@OutputerFormats.register("html")
class HTMLOutputer(BaseOutputer):

    table_packages_tpl = """
<style>
    table, th, td {{
        border: 1px solid black;
        border-collapse: collapse;
    }}
    .selected {{
        border: 3px solid black;
    }}
</style>

<script type="text/javascript">
    function handleEvent(id) {{
        selected = document.getElementsByClassName('selected');
        if (selected[0]) selected[0].className = '';
        cell = document.getElementById(id);
        cell.className = 'selected';
        elem = document.getElementById('SelectedPackage');
        elem.innerHTML = id;
    }}
</script>

<h1>{title}</h1>

{content}

<br>Selected: <div id="SelectedPackage"></div>

<br>Legend<br>
<table><tr><td bgcolor=#ffff00>&nbsp;&nbsp;&nbsp;&nbsp;</td><td>Outdated from recipe</td></tr>
<tr><td bgcolor=#00ff00>&nbsp;&nbsp;&nbsp;&nbsp;</td><td>Updated</td></tr>
<tr><td>&nbsp;&nbsp;&nbsp;&nbsp;</td><td>Non existing</td></tr></table>  
"""

    def search_packages(self, info, query, output_filepath, out, outdated, *args, **kwargs):

        def get_coordinates(settings, options):
            # Only settings to build row_name: os, compiler
            row_name = "{os} {compiler} {compiler_version}".\
                format(os=settings.pop('os', 'None'),
                       compiler=settings.pop('compiler', 'None'),
                       compiler_version=settings.pop('compiler.version', 'None')
                       )
            extra_row = " ".join(["({})".format(settings.pop(it)) for it in settings.keys()
                                  if it.startswith('compiler')])
            row_name += extra_row

            # Column name:
            column_name = " ".join(settings.values())
            extra_column = "<br/>".join(["{}={}".format(k, v) for k, v in options.items()])
            column_name = column_name + "<br/>" + extra_column
            return row_name, column_name

        binary = namedtuple("Binary", "id outdated")
        content = []
        for remote_info in info['results']:
            remote = remote_info.get('remote')
            if remote and remote != 'None':
                content.append("<h2>'{}'</h2>".format(remote_info['remote']))

            data = defaultdict(dict)
            columns = set()
            for package in remote_info['items'][0]['packages']:
                row, column = get_coordinates(package.get('settings', {}),
                                              package.get('options', {}))
                data[row][column] = binary(id=package['id'], outdated=package.get('outdated', None))
                columns.add(column)

            # Print table (ordered columns)
            headers = sorted(columns)
            with html("table", content) as content:
                with html("thead", content) as content:
                    with html("tr", content) as content:
                        content.append("<th></th>")
                        for h in headers:
                            content.append("<th>{}</th>".format(h))

                for row, values in data.items():
                    with html("tr", content) as content:
                        content.append("<td>{}</td>".format(row))
                        for h in headers:
                            value = values.get(h, None)
                            if value:
                                color = "#ffff00" if value.outdated else "#00ff00"
                                content.append('<td bgcolor={color} id="{id}" '
                                               'onclick=handleEvent("{id}")></td>'.
                                               format(id=value.id, color=color))
                            else:
                                content.append("<td></td>")

        context = {'title': query, 'content': "\n".join(content)}
        html_contents = self.table_packages_tpl.format(**context)
        save(output_filepath, html_contents)
        out.writeln("")
        out.info("HTML file created at '{}'".format(output_filepath))


