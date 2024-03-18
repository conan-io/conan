graph_info_html = r"""
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
                    <input type="checkbox" onchange="showPackageType()" id="show_package_type"/>
                    <label for="show_package_type">Show package type</label>
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
                <div id="error" style="padding:10;" class="noPrint"></div>
            </div>
        </div>

        <script type="text/javascript">
            const graph_data = {{ deps_graph }};
            var hide_build = false;
            var hide_test = false;
            var search_pkg = null;
            var collapse_build = false;
            var show_package_type = false;
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
            var global_edges = {};
            function define_data(){
                var nodes = [];
                var edges = [];
                var collapsed_build = {};
                var targets = {};
                global_edges = {};
                global_nodes = {};
                var edge_counter = 0;
                if (graph_data["error"]){
                    if (graph_data["error"]["type"] == "conflict"){
                        var conflict = graph_data["error"]["conflict"]; // id and ref
                        var branch1 = graph_data["error"]["branch1"]; // id and ref
                        var branch2 = graph_data["error"]["branch2"]; // id and ref
                    }
                }
                for (const [node_id, node] of Object.entries(graph_data["nodes"])) {
                    if (node.context == "build" && hide_build) continue;
                    if (node.test && hide_test) continue;
                    if (collapse_build) {
                        var existing = collapsed_build[label];
                        targets[node_id] = existing;
                        if (existing) continue;
                        collapsed_build[label] = node_id;
                    }
                    const shape = node.context == "build" || node.test ? "ellipse" : "box";
                    if (node["name"])
                        var label =  node["name"] + "/" + node["version"];
                    else if (node["ref"])
                        var label = node["ref"];
                    else
                        var label = node.recipe == "Consumer"? "conanfile": "CLI";
                    if (show_package_type) {
                         label = "<b>" + label + "\n" + "<i>" + node.package_type + "</i>";
                    }

                    borderWidth = 1;
                    borderColor = "SkyBlue";
                    font = {multi: 'html'};
                    shapeProperties = {};
                    var color = color_map[node.binary]
                    if (conflict && conflict.id == node_id){
                        font.color = "white";
                        color = "Black";
                    }
                    if (search_pkg && label.match(search_pkg)) {
                        borderWidth = 3;
                        borderColor = "Magenta";
                    }
                    if (node.test) {
                        font.background = "lightgrey";
                        shapeProperties = {borderDashes: true};
                    }
                    if (node.recipe == "Platform") {
                        font.background = "Violet";
                    }
                    nodes.push({
                        id: node_id,
                        font: font,
                        label: label,
                        shape: shape,
                        shapeProperties: shapeProperties,
                        borderWidth: borderWidth,
                        color: {border: borderColor, background: color,
                                highlight: {background: color, border: "Blue"}},
                    });
                }
                for (const [node_id, node] of Object.entries(graph_data["nodes"])) {
                    for (const [dep_id, dep] of Object.entries(node["dependencies"])) {
                        if (dep.direct){
                            var target_id = targets[dep_id] || dep_id;
                            edges.push({id: edge_counter, from: node_id, to: target_id,
                                        color: {color: "SkyBlue", highlight: "Blue"}});
                            global_edges[edge_counter] = dep;
                            edge_counter++;
                        }
                    }
                }
                if (conflict && branch2) {
                    nodes.push({
                        id: "conflict",
                        font: {color: "white"},
                        label: conflict.ref,
                        shape: "circle",
                        color: {background: "black",
                                highlight: {background: "black", border: "Blue"}},
                    });
                    nodes.push({
                        id: "branch2",
                        font: {color: "white"},
                        label: branch2.ref,
                        shape: "box",
                        color: {background: "black",
                                highlight: {background: "black", border: "Blue"}},
                    });
                    edges.push({from: branch2.id, to: "branch2",
                                color: {color: "SkyBlue", highlight: "Blue"}});
                    edges.push({from: "branch2", to: "conflict",
                                color: {color: "Red", highlight: "Red"}});
                    edges.push({from: conflict.id, to: "conflict",
                                color: {color: "Red", highlight: "Red"}});
                }
                var nodes = new vis.DataSet(nodes);
                var edges = new vis.DataSet(edges);
                var data = {nodes: nodes, edges: edges};
                return data;
            };
            function define_legend() {
                var x = 0;
                var y = 0;
                var step = 250;
                var legend_nodes = [];
                legend_nodes.push({id: 0, x: x, y: y, shape: "box", font: {size: 35},
                    label: "require",
                });
                legend_nodes.push({id: 1, x: x + step, y: y, font: {size: 35}, shape: "ellipse",
                    label: "tool-require",
                });
                legend_nodes.push({id: 2, x: x + 2* step, y: y, font: {size: 35, background: "lightgrey"},
                    shape: "ellipse", shapeProperties: {borderDashes: true},
                    label: "test-require",
                })
                var counter = 3;
                legend_nodes.push({x: x + counter*step, y: y, shape: "ellipse",
                    label: "platform",
                    font: {size: 35, background: "Violet"},
                });
                counter++;
                for (const [status, color] of Object.entries(color_map)) {
                    legend_nodes.push({x: x + counter*step, y: y, shape: "box", font: {size: 35},
                        label: status,
                        color: {border: "SkyBlue", background: color}
                    });
                    counter++;
                }
                legend_nodes.push({x: x + counter*step, y: y, shape: "box",
                    label: "conflict",
                    font: {size: 35, color: "white"},
                    color: {border: "SkyBlue", background: "Black"}
                });
                return {nodes: new vis.DataSet(legend_nodes)};
            }
            var error = document.getElementById("error");
            if (graph_data["error"]){
                 let div = document.createElement('div');
                 div.innerHTML = "<pre>Error in the graph: " + JSON.stringify(graph_data["error"], undefined, 2) + "</pre>";
                 error.appendChild(div);
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
                nodes: {font: {'face': 'monospace', 'align': 'left'}},
                layout: {
                    "hierarchical": {
                        enabled: true,
                        sortMethod: "directed",
                        direction: "DU",
                        nodeSpacing: 170,
                        blockShifting: true,
                        edgeMinimization: true,
                        shakeTowards: "roots",
                    }
                },
                physics: { enabled: false},
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
                var ids_edges = properties.edges;
                var control = document.getElementById("details");
                while (control.firstChild) {
                    control.removeChild(control.firstChild);
                }
                if(ids[0] || ids_edges[0]) {
                    selected = graph_data["nodes"][ids[0]] || global_edges[ids_edges[0]];
                    let div = document.createElement('div');
                    let f = Object.fromEntries(Object.entries(selected).filter(([_, v]) => v != null));
                    div.innerHTML = "<pre>" + JSON.stringify(f, undefined, 2) + "</pre>";
                    control.appendChild(div);
                }
                else {
                    control.innerHTML = "<b>Info</b>: Click on a package or edge for more info";
                }
            });
            function draw() {
                var scale = network.getScale();
                var viewPos = network.getViewPosition();
                data = define_data();
                network.setData(data);
                network.redraw();
                network.moveTo({position: viewPos, scale: scale});
            }
            function switchBuild() {
                hide_build = !hide_build;
                draw();
            }
            function switchTest() {
                hide_test = !hide_test;
                draw();
            }
            function collapseBuild() {
                collapse_build = !collapse_build;
                draw();
            }
            function searchPackage(e) {
                search_pkg = e.value;
                draw();
            }
            function showPackageType(e) {
                show_package_type = !show_package_type;
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
</html>
"""
