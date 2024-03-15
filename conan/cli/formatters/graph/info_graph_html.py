graph_info_html = """
<html lang="en">
    <head>
        <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/dist/vis-network.min.js"></script>
    </head>

    <body>
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

        <div style="display: grid; grid-template-columns: 75% 25%; grid-template-rows: 30px auto; height: 100vh;">
            <div id="mylegend" style="background-color: lightgrey; grid-column-end: span 2;"></div>
            <div id="mynetwork"></div>
            <div style="background-color: lightgrey;min-height:100%;height:0;overflow-y: auto;">
                <div>
                    <input type="checkbox" onchange="switchBuild()" id="show_build_requires" checked />
                    <label for="show_build_requires">Show build-requires</label>
                </div>
                <div>
                    <input type="checkbox" onchange="switchTest()" id="show_test_requires" checked />
                    <label for="show_test_requires">Show test-requires</label>
                </div>
                <div>
                    <input type="checkbox" onchange="collapseBuild()" id="group_build_requires"/>
                    <label for="group_build_requires">Group build-requires</label>
                </div>
                 <div>
                    <input type="search" placeholder="Search package..." oninput="searchPackage(this)">
                </div>
                <div>
                    <input type="checkbox" onchange="showhideclass('controls')" id="show_controls"/>
                    <label for="show_controls">Show graph controls</label>
                </div>
                <div id="controls" class="controls" style="padding:5; display:none"></div>
                <div id="details"  style="padding:10;" class="noPrint">Package info: Click on one package to show information</div>
            </div>
        </div>

        <script type="text/javascript">
            const graph_data = {{ deps_graph }};
            var hide_build = false;
            var hide_test = false;
            var search_pkg = null;
            var collapse_build = false;
            var color_map = {Cache: "SkyBlue",
                             Download: "LightGreen",
                             Build: "Yellow",
                             Missing: "Orange",
                             Update: "SeaGreen",
                             Skip: "White",
                             Editable: "LightCyan",
                             EditableBuild: "Cyan",
                             Invalid: "Red",
                             Platform: "Violet"};
            function define_data(){
                var nodes = [];
                var edges = [];
                var collapsed_build = {};
                var targets = {};
                for (const [node_id, node] of Object.entries(graph_data["nodes"])) {
                    if (node.context == "build" && hide_build) continue;
                    if (node.test && hide_test) continue;
                    const shape = node.context == "build" ? "ellipse" : node.test ? "hexagon" : "box";
                    var label =  node["name"] + "/" + node["version"];
                    var color = color_map[node.binary]
                    if (collapse_build) {
                        var existing = collapsed_build[label];
                        targets[node_id] = existing;
                        if (existing) continue;
                        collapsed_build[label] = node_id;
                    }
                    if (node["name"] == search_pkg){
                        borderWidth = 3;
                        borderColor = "Red"
                    }
                    else {
                        borderWidth = 1;
                        borderColor = "SkyBlue";
                    }
                    nodes.push({
                        id: node_id,
                        label: label,
                        shape: shape,
                        borderWidth: borderWidth,
                        color: {border: borderColor, background: color,
                                highlight: {background: color, border: borderColor}},
                    });
                }
                for (const [node_id, node] of Object.entries(graph_data["nodes"])) {
                    for (const [dep_id, dep] of Object.entries(node["dependencies"])) {
                        if (dep.direct){
                            var target_id = targets[dep_id] || dep_id;
                            edges.push({from: node_id, to: target_id, color: "SkyBlue"});
                        }
                    }
                }
                var nodes = new vis.DataSet(nodes);
                var edges = new vis.DataSet(edges);
                var data = {nodes: nodes, edges: edges};
                return data;
            };
            function define_legend() {
                var x = -300;
                var y = -200;
                var step = 250;
                var legend_nodes = [];
                legend_nodes.push({id: 0, x: x, y: y, shape: "box", font: {size: 35},
                    label: "require",
                });
                legend_nodes.push({id: 1, x: x + step, y: y, font: {size: 35}, shape: "ellipse",
                    label: "tool-require",
                });
                legend_nodes.push({id: 2, x: x + 2* step, y: y, font: {size: 35, background: "grey"},
                    shape: "ellipse", shapeProperties: {borderDashes: true},
                    label: "test-require",
                })
                var counter = 3;
                for (const [status, color] of Object.entries(color_map)) {
                    legend_nodes.push({x: x + counter*step, y: y, shape: "box", font: {size: 35},
                        label: status,
                        color: {border: "SkyBlue", background: color}
                    });
                    counter++;
                }
                return {nodes: new vis.DataSet(legend_nodes)};
            }

            var container = document.getElementById('mynetwork');
            var controls = document.getElementById('controls');
            var legend_container = document.getElementById('mylegend');

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
                        edgeMinimization: true,
                        shakeTowards: "roots",
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

            var data = define_data();
            var network = new vis.Network(container, data, options);
            var legend_data = define_legend();
            var options_legend = {interaction: {selectable: false, dragView: false, dragNodes: false,
                                                zoomView: false}, physics: {enabled: false}};
            var legend = new vis.Network(legend_container, legend_data, options_legend);

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
                data = define_data();
                network.setData(data);
                draw();
            }
            function switchTest() {
                hide_test = !hide_test;
                data = define_data();
                network.setData(data);
                draw();
            }
            function collapseBuild() {
                collapse_build = !collapse_build;
                console.log("collapsing build");
                data = define_data();
                network.setData(data);
                draw();
            }
            function searchPackage(e) {
                search_pkg = e.value;
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
