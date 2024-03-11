graph_info_html = """
<html lang="en">
    <head>
        <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/dist/vis-network.min.js"></script>
    </head>

    <body>
        <script type="text/javascript">

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

        <div style="width: 100%;">
            <div id="mynetwork" style="float:left; width: 75%;"></div>
            <div style="float:right;width:25%;">
                <div>
                    <input type="checkbox" onchange="switchBuild()" id="show_build_requires" checked />
                    <label for="show_build_requires">Show build-requires</label>
                </div>
                <div>
                    <input type="checkbox" onchange="collapseBuild()" id="group_build_requires"/>
                    <label for="group_build_requires">Group build-requires</label>
                </div>

                <div id="details"  style="padding:10;" class="noPrint">Package info: no package selected</div>
                <button onclick="javascript:showhideclass('controls')" class="button noPrint">
                    Show / hide graph controls
                </button>
                <div id="controls" class="controls" style="padding:5; display:none"></div>
            </div>
        </div>
        <div style="clear:both"></div>

        <script type="text/javascript">

            const graph_data = {{ deps_graph }};
            var hide_build = false;
            var collapse_build = false;

            function define_data(){
                var nodes = [];
                var edges = [];
                var collapsed_build = {};
                var targets = {};
                for (const [node_id, node] of Object.entries(graph_data["nodes"])) {
                    const shape = node.context == "build" ? "ellipse" : node.test ? "hexagon" : "box";
                    var label =  node["name"] + "/" + node["version"];
                    if (collapse_build) {
                        var existing = collapsed_build[label];
                        targets[node_id] = existing;
                        if (existing) continue;
                        collapsed_build[label] = node_id;
                    }
                    nodes.push({
                        id: node_id,
                        label: label,
                        shape: shape
                    });

                }
                for (const [node_id, node] of Object.entries(graph_data["nodes"])) {
                    for (const [dep_id, dep] of Object.entries(node["dependencies"])) {
                        if (dep.direct){
                            var target_id = targets[dep_id] || dep_id;
                            edges.push({from: node_id, to: target_id});
                        }
                    }
                }
                var nodes = new vis.DataSet(nodes);
                var edges = new vis.DataSet(edges);
                var data = {nodes: nodes, edges: edges};
                return data;
            };

            var container = document.getElementById('mynetwork');
            var controls = document.getElementById('controls');

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
                        "direction": "DU",
                        nodeSpacing: 170,
                        blockShifting: true,
                        edgeMinimization: true
                    }
                },
                physics: {
                    enabled: false,
                },
                configure: {
                    enabled: true,
                    filter: 'layout',
                    showButton: false,
                    container: controls
                }
            };

            var data = define_data();
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
                        if (value) {
                            let li = document.createElement('li');
                            li.innerHTML = "<b>"+ key +"</b>: " + value;
                            ul.appendChild(li);
                        }
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
            function switchBuild() {
                hide_build = !hide_build;
                nodes_update = [];
                for (const [node_id, node] of Object.entries(graph_data["nodes"])) {
                    if (node.context == "build")
                        nodes_update.push({id: node_id, hidden: hide_build})
                }
                data.nodes.update(nodes_update);
                draw();
            }
            function collapseBuild() {
                collapse_build = !collapse_build;
                console.log("collapsing build");
                data = define_data();
                network.setData(data);
                draw();
            }
            function showhideclass(id) {
                var elements = document.getElementsByClassName(id)
                for (var i = 0; i < elements.length; i++) {
                    elements[i].style.display = (elements[i].style.display != 'none') ? 'none' : 'block';
                }
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
