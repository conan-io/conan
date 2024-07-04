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
                var yOffset = 50;

                var posX = 0;
                var posY = 0;
                var columns = 4;

                buildOrderData.forEach((step, stepIndex) => {
                    var stepId = 'step' + stepIndex;
                    elements.push({
                        data: { id: stepId, label: 'Step ' + (stepIndex + 1) },
                        position: { x: posX, y: posY }
                    });

                    step.forEach((lib, libIndex) => {
                        var libId = stepId + '_lib' + libIndex;
                        var libLabel = lib.ref.split('#')[0];

                        if ((libIndex + 1) % columns === 0) {
                            posX = 0;
                            posY += yOffset; // move to the next row
                        }

                        elements.push({
                            data: { id: libId, parent: stepId, label: libLabel},
                            position: { x: posX + libLabel.length/2.0 * 12, y: posY}
                        });
                        posX += libLabel.length * 12;
                    });

                    if (stepIndex > 0) {
                        var prevStepId = 'step' + (stepIndex - 1);
                        edges.push({ data: { id: prevStepId + '_to_' + stepId, source: prevStepId, target: stepId } });
                    }

                    posY = posY + yOffset * 2;
                    posX = 0;
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
                                'padding': '5px',
                                'font-family': 'monospace'
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
                                'padding': 10,
                                'font-family': 'monospace'
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
                        padding: 5,
                        fit: true
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
