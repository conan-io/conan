graph_info_html = """
<html lang="en">
    <head>
        <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/dist/vis-network.min.js"></script>
    </head>

    <body>
        <script type="text/javascript">
            function showhideclass(id) {
                var elements = document.getElementsByClassName(id)
                for (var i = 0; i < elements.length; i++) {
                    elements[i].style.display = (elements[i].style.display != 'none') ? 'none' : 'block';
                }
            }
        </script>
        <style>
            @media print {
                .noPrint {
                    display: none;
                }
            }
            .button {
                background-color: #5555cc;
                border: none;
                color: white;
                padding: 5px 10px;
                text-align: center;
                text-decoration: none;
                display: inline-block;
                font-size: 18px;
            }
        </style>

        <script type="application/json" id="graph_data">
            {{ deps_graph }}
        </script>

        <div style="width: 100%;">
            <div id="mynetwork" style="float:left; width: 75%;"></div>
                <button onclick="javascript:switchBuild()" class="button noPrint">
                    Show / hide build-requires
                </button>
                <div style="float:right;width:25%;">
                <div id="details"  style="padding:10;" class="noPrint">Package info: no package selected</div>
                <button onclick="javascript:showhideclass('controls')" class="button noPrint">
                    Show / hide graph controls
                </button>
                <div id="controls" class="controls" style="padding:5; display:none"></div>
            </div>
        </div>
        <div style="clear:both"></div>

        <script type="text/javascript">
            var graph_data = JSON.parse(document.getElementById('graph_data').innerHTML);
            var hide_build = false;
            var nodes = [];
            var edges = [];
            for (const [node_id, node] of Object.entries(graph_data["nodes"])) {
                const shape = node.context == "build" ? "ellipse" : node.test ? "hexagon" : "box";
                nodes.push({
                    id: node_id,
                    label: node["name"],
                    shape: shape
                });
                for (const [dep_id, dep] of Object.entries(node["dependencies"])) {
                    if (dep.direct)
                        edges.push({from: node_id, to: dep_id});
                }
            }

            var nodes = new vis.DataSet(nodes);
            var edges = new vis.DataSet(edges);
            var container = document.getElementById('mynetwork');
            var controls = document.getElementById('controls');
            var data = {
                nodes: nodes,
                edges: edges
            };
            var options = {
                autoResize: true,
                locale: 'en',
                edges: {
                    arrows: { to: {enabled: true} },
                    smooth: { enabled: false}
                },
                nodes: {
                    font: {'face': 'monospace', 'align': 'left'}
                },
                layout: {
                    "hierarchical": {
                        "enabled": true,
                        "sortMethod": "directed",
                        "direction": "UD",
                        nodeSpacing: 200
                    }
                },
                physics: {
                    enabled: false,
                },
                configure: {
                    enabled: true,
                    filter: 'layout physics',
                    showButton: false,
                    container: controls
                }
            };
            function switchBuild() {
                hide_build = !hide_build;
                nodes_update = [];
                for (const [node_id, node] of Object.entries(graph_data["nodes"])) {
                    if (node.context == "build")
                        nodes_update.push({id: node_id, hidden: hide_build})
                }
                nodes.update(nodes_update);
                draw();
            }
            var network = new vis.Network(container, data, options);
            network.on('click', function (properties) {
                var ids = properties.nodes;
                var control = document.getElementById("details");
                while (control.firstChild) {
                    control.removeChild(control.firstChild);
                }
                if(ids[0]) {
                    selected_node = graph_data["nodes"][ids[0]]
                    let ul = document.createElement('ul');
                    for (const [key, value] of Object.entries(selected_node)) {
                        let li = document.createElement('li');
                        li.innerHTML = "<b>"+ key +"</b>: " + value;
                        ul.appendChild(li);
                    }
                    control.appendChild(ul);
                }
                else {
                    control.innerHTML = "<b>Package info</b>: No package selected";
                }
            });
            function draw() {
                network.redraw();
            }
            window.addEventListener("load", () => {
              draw();
            });
        </script>
    </body>
    <footer>
        <div class="container-fluid">
            <div class="info">
                <p>
                      Conan <b>v{{ version  }}</b> <script>document.write(new Date().getFullYear())</script> JFrog LTD. <a>https://conan.io</a>
                </p>
            </div>
        </div>
    </footer>
</html>
"""
