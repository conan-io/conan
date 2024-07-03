import os
from jinja2 import select_autoescape, Template
from conan.api.output import cli_out_write

build_order_html = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mermaid Diagram</title>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({ startOnLoad: true });
    </script>
    <style>
        .mermaid {
            width: 100%;
            height: 100vh;
        }
    </style>
</head>
<body>
    <div class="mermaid">
        graph TD;
        %% Step definitions
        {{ mermaid_content }}
    </div>
</body>
</html>
"""


def _prepare_mermaid_content(build_order):
    content = ""
    for index, step in enumerate(build_order):
        content += f"subgraph Step{index + 1}\n"
        content += "direction TB\n"
        for row in range(0, len(step), 4):
            row_libs = step[row:row + 4]
            row_content = "\n".join([
                                        f"{lib['ref'].replace('/', '_').replace('.', '_').split('#')[0]}[\"{lib['ref'].split('#')[0]}\"]"
                                        for lib in row_libs])
            content += f"{row_content}\n"
        content += "end\n"

    for step_index in range(len(build_order) - 1):
        content += f"Step{step_index + 1} --> Step{step_index + 2}\n"

    return content


def _render_build_order(build_order, template):
    from conans import __version__ as client_version
    mermaid_content = _prepare_mermaid_content(build_order)
    context = {
        'mermaid_content': mermaid_content,
        'version': client_version,
    }
    return template.render(context)


def format_build_order_html(build_order):
    build_order = build_order["order"] if isinstance(build_order, dict) else build_order
    template = Template(build_order_html, autoescape=select_autoescape(['html', 'xml']))
    cli_out_write(_render_build_order(build_order, template))
