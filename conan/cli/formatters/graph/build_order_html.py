import os
from jinja2 import select_autoescape, Template
from conan.api.output import cli_out_write

build_order_html = r"""
<html lang="en">
    <head>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.30.0/cytoscape.min.js" integrity="sha512-zHc90yHSbkgx0bvVpDK/nVgxANlE+yKN/jKy91tZ4P/vId8AL7HyjSpZqHmEujWDWNwxYXcfaLdYWjAULl35MQ==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.2.3/dist/css/bootstrap.min.css" rel="stylesheet"
              integrity="sha384-rbsA2VBKQhggwzxH7pPCaAqO46MgnOM80zW1RWuH61DGLwZJEdK2Kadq2F9CUG65" crossorigin="anonymous">
    </head>

    <body>
        <style>
            body {
              font: 16px helvetica neue, helvetica, arial, sans-serif;
              display: flex;
              margin: 0;
              padding: 0;
              height: 100vh;
            }

            .sidebar {
              background: #f9f9f9;
              border-right: 1px solid #ccc;
              padding: 20px;
              box-sizing: border-box;
              overflow-y: auto;
              font-size: 16px;
            }

            .content {
              flex-grow: 1;
              display: flex;
              flex-direction: column;
              overflow: hidden;
            }

            #cy {
              flex-grow: 0.8;
            }

            #node-info {
              margin-top: 20px;
              background: #f9f9f9;
              padding: 10px;
              font-family: monospace;
              white-space: pre-wrap;  /* Makes the text wrap */
              font-size: 22px;
              word-wrap: break-word; /* Ensures long words break and wrap */
            }
        </style>

        <div class="d-flex w-100 h-100">
            <div class="sidebar col-md-4 col-lg-3">
                <div id="node-info">
                    <p>Click on a node to see details.</p>
                </div>
            </div>
            <div class="content col-md-8 col-lg-9">
                <div id="cy"></div>
            </div>
        </div>

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

                        // Determine the type of the library
                        var libData = Array.isArray(lib.packages) ? lib.packages[0][0] : lib;
                        var libType = libData.binary || libData.build || libData.cache;

                        var nodeColor;
                        if (libType === "Build") {
                            nodeColor = "#FFCC80"; // Light orange
                        } else if (libType === "Cache") {
                            nodeColor = "#A5D6A7"; // Light green
                        } else {
                            nodeColor = "#B2DFDB"; // Default color
                        }

                        if ((libIndex + 1) % columns === 0) {
                            posX = 0;
                            posY += yOffset; // move to the next row
                        }

                        elements.push({
                            data: { id: libId, parent: stepId, label: libLabel, info: lib, color: nodeColor },
                            position: { x: posX + libLabel.length / 2.0 * 12, y: posY }
                        });
                        posX += libLabel.length * 12 + 20; // Adding extra spacing between nodes
                    });

                    if (stepIndex > 0) {
                        var prevStepId = 'step' + (stepIndex - 1);
                        edges.push({ data: { id: prevStepId + '_to_' + stepId, source: prevStepId, target: stepId } });
                    }

                    posY += yOffset * 2;
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
                                'background-color': 'data(color)',
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

                // Add click event listener to nodes
                cy.on('tap', 'node', function(evt){
                    var node = evt.target;
                    var info = node.data('info');
                    var infoHtml = '';
                    for (var key in info) {
                        if (info.hasOwnProperty(key)) {
                            infoHtml += '<p><strong>' + key + ':</strong> ' + JSON.stringify(info[key], null, 2) + '</p>';
                        }
                    }
                    document.getElementById('node-info').innerHTML = infoHtml;
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
