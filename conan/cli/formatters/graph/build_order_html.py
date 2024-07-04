import os
from jinja2 import select_autoescape, Template
from conan.api.output import cli_out_write

build_order_html = r"""
<html lang="en">
    <head>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.0/cytoscape.min.js" integrity="sha512-zHc90yHSbkgx0bvVpDK/nVgxANlE+yKN/jKy91tZ4P/vId8AL7HyjSpZqHmEujWDWNwxYXcfaLdYWjAULl35MQ==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
    </head>

    <body>
        <style>
            body {
              font: 14px helvetica neue, helvetica, arial, sans-serif;
            }

            #cy {
              height: 100vh;
              width: 100vw;
              position: absolute;
              left: 0;
              top: 0;
            }
        </style>

        <div id="cy"></div>

        <script type="text/javascript">
            document.addEventListener("DOMContentLoaded", function() {
                var buildOrderData = {{ build_order | tojson }};

                var elements = [];
                var edges = [];
                var positions = { x: 100, y: 50 };
                var yOffset = 100;

                buildOrderData.forEach((step, stepIndex) => {
                    var stepId = 'step' + stepIndex;
                    elements.push({
                        data: { id: stepId, label: 'Step ' + (stepIndex + 1) },
                        position: { x: positions.x, y: positions.y + stepIndex * yOffset }
                    });

                    step.forEach((lib, libIndex) => {
                        var libId = stepId + '_lib' + libIndex;
                        elements.push({
                            data: { id: libId, parent: stepId, label: lib.ref.split('#')[0] },
                            position: { x: positions.x + (libIndex + 1) * 150, y: positions.y + stepIndex * yOffset }
                        });
                    });

                    if (stepIndex > 0) {
                        var prevStepId = 'step' + (stepIndex - 1);
                        edges.push({ data: { id: prevStepId + '_to_' + stepId, source: prevStepId, target: stepId } });
                    }
                });

                var cy = cytoscape({
                    container: document.getElementById('cy'),
                    boxSelectionEnabled: false,
                    style: [
                        {
                            selector: 'node',
                            style: {
                                'shape': 'rectangle',
                                'content': 'data(label)',
                                'text-valign': 'center',
                                'text-halign': 'center',
                                'background-color': '#B2DFDB',
                                'border-color': '#00695C',
                                'border-width': 1,
                                'width': 'label',
                                'height': 'label',
                                'padding': '5px'
                            }
                        },
                        {
                            selector: ':parent',
                            style: {
                                'text-valign': 'top',
                                'text-halign': 'center',
                                'shape': 'round-rectangle',
                                'background-opacity': 0.1,
                                'border-color': '#004D40',
                                'border-width': 2,
                                'padding': 10
                            }
                        },
                        {
                            selector: 'edge',
                            style: {
                                'curve-style': 'bezier',
                                'target-arrow-shape': 'triangle',
                                'line-color': '#004D40',
                                'target-arrow-color': '#004D40',
                                'width': 2
                            }
                        }
                    ],
                    elements: {
                        nodes: elements,
                        edges: edges
                    },
                    layout: {
                        name: 'preset',
                        padding: 5
                    }
                });
            });
        </script>
    </body>
</html>
"""


def _render_build_order(build_order, template):
    from conans import __version__ as client_version
    context = {
        'build_order': build_order,
        'version': client_version,
    }
    return template.render(context)


def format_build_order_html(build_order):
    build_order = build_order["order"] if isinstance(build_order, dict) else build_order
    template = Template(build_order_html, autoescape=select_autoescape(['html', 'xml']))
    cli_out_write(_render_build_order(build_order, template))
