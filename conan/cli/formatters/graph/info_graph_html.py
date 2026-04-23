graph_info_html = r"""
<html lang="en">
    <head>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/vis-network/9.1.9/standalone/umd/vis-network.min.js" integrity="sha512-iTgTmIgxyA2YehKNVbzLJx4j9SnuC5ihtRrtxVkXH/9nF3vXBN5YeNQp+6wufBWKD3u+roHVNOvWBMufQnBbug==" crossorigin="anonymous" referrerpolicy="no-referrer"></script>
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
            label {
                user-select: none
            }

            #container {
                display: grid;
                grid-template-columns: 75% 25%;
                grid-template-rows: 50px auto;
                height: 100vh;
            }
            #mylegend {
                border-bottom: 2px solid #f2f2f2;
                grid-column-end: span 1;
                font-size: 14px;
                height: 100%;
            }
            #empty-sidebar, #sidebar {
                background-color: #f9f9fe;
                border: none;
                min-height:100%;
                height:0;
                overflow-y: auto;
                padding: 5px 10px;
            }
            #details {
                background-color: #f3f3f3;
                overflow-y: auto;
                border: 1px solid #e4e4e4;
                border-radius: 5px;
                padding: 3px 5px;
            }
        </style>

        <div id="container">
            <div id="mylegend"></div>
            <div id="empty-sidebar">
                <h3>Controls</h3>
            </div>
            <div id="mynetwork"></div>
            <div id="sidebar">
                <div>
                    <input type="checkbox" onchange="switchBuild()" id="show_build_requires" checked />
                    <label for="show_build_requires">Show build-requires</label>
                </div>
                <div>
                    <input type="checkbox" onchange="switchTest()" id="show_test_requires" checked />
                    <label for="show_test_requires">Show test-requires</label>
                </div>
                <div>
                    <input type="checkbox" onchange="switchTransitive()" id="show_transitive_requires"/>
                    <label for="show_transitive_requires">Show transitive-requires</label>
                </div>
                <div>
                    <input type="checkbox" onchange="collapsePackages()" id="collapse_packages"/>
                    <label for="collapse_packages">Group packages</label>
                </div>
                <div>
                    <input type="checkbox" onchange="showPackageType()" id="show_package_type"/>
                    <label for="show_package_type">Show package type</label>
                </div>
                <div>
                    <input type="checkbox" onchange="showSubgraph()" id="show_subgraph"/>
                    <label for="show_package_type">Show subgraph</label>
                </div>
                <div>
                    <input type="search" placeholder="Search packages..." oninput="searchPackages(this)" onkeydown="onSearchKeyDown(event)">
                </div>
                <div>
                    <input type="search" placeholder="Exclude packages..." title="Add a comma to exclude an additional package" oninput="excludePackages(this)">
                </div>
                <div>
                    <details>
                    <summary>Extra graph controls</summary>
                    <div id="controls" class="controls" style="padding: 5;"></div>
                    </details>
                </div>

                <div id="details-container" style="padding:10;" class="noPrint">
                    <h3>Information</h3>
                    <div id="details">
                    Click on one package or edge to show information
                    </div>
                </div>
                <div id="error" style="padding:10;" class="noPrint"></div>
            </div>
        </div>

        <script type="text/javascript">
            const graph_data = {{ deps_graph | tojson }};
            let hide_build = false;
            let hide_test = false;
            let show_transitive = false;
            let search_pkgs = null;
            let focus_search = false;
            let excluded_pkgs = null;
            let collapse_packages = false;
            let show_package_type = false;
            let show_subgraph = false;
            let color_map = {Cache: "SkyBlue",
                             Download: "LightGreen",
                             Build: "Yellow",
                             Missing: "Orange",
                             Update: "SeaGreen",
                             Skip: "White",
                             Editable: "LightCyan",
                             EditableBuild: "Cyan",
                             Invalid: "Red",
                             Platform: "Violet"};
            let global_edges = {};
            let collapsed_packages = null;
            function define_data(){
                let nodes = [];
                let edges = [];
                collapsed_packages = {"build": {}, "host": {}};
                let targets = {};
                global_edges = {};
                let edge_counter = Math.max(...Object.keys(graph_data["nodes"])) + 1;
                let conflict=null;
                let provide_conflict=null;
                let missing_error=null;
                let loop_error=null;
                if (graph_data["error"] && graph_data["error"]["type"] == "conflict")
                    conflict = graph_data["error"];
                else if (graph_data["error"] && graph_data["error"]["type"] == "provide_conflict")
                    provide_conflict = graph_data["error"];
                else if (graph_data["error"] && graph_data["error"]["type"] == "missing")
                    missing_error = graph_data["error"];
                else if (graph_data["error"] && graph_data["error"]["type"] == "loop")
                    loop_error = [graph_data["error"]['node']['label'], graph_data["error"]['require']['name']];
                for (const [node_id, node] of Object.entries(graph_data["nodes"])) {
                    if (node.context == "build" && hide_build) continue;
                    if (node.test && hide_test) continue;
                    let shape = node.context == "build" || node.test ? "ellipse" : "box";
                    let label = getNodeLabel(node);
                    if (collapse_packages) {
                        let existing = collapsed_packages[node.context][label];
                        targets[node_id] = existing;
                        if (existing) continue;
                        collapsed_packages[node.context][label] = node_id;
                    }
                    if (excluded_pkgs) {
                        let patterns = excluded_pkgs.split(',')
                            .map(pattern => pattern.trim())
                            .filter(pattern => pattern.length > 0)
                            .map(pattern => pattern.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&'));
                        if (patterns.some(pattern => label.match(pattern))) {
                            continue;
                        }
                    }
                    if (show_package_type) {
                         label = "<b>" + label + "\n" + "<i>" + node.package_type + "</i>";
                    }
                    borderWidth = 1;
                    borderColor = "SkyBlue";
                    font = {multi: 'html'};
                    shapeProperties = {};
                    let color = color_map[node.binary]
                    if (conflict && conflict.branch1.dst_id == node_id){
                        font.color = "white";
                        color = "Black";
                        shape = "circle";
                    }
                    if (provide_conflict && provide_conflict.node.id == node_id){
                        font.color = "white";
                        color = "Black";
                        shape = "circle";
                    }
                    if (search_pkgs) {
                        let patterns = search_pkgs.split(',')
                            .map(pattern => pattern.trim())
                            .filter(pattern => pattern.length > 0)
                            .map(pattern => pattern.replace(/[-\/\\^$*+?.()|[\]{}]/g, '\\$&'));
                        if (patterns.some(pattern => label.match(pattern))) {
                            borderWidth = 3;
                            borderColor = "Magenta";
                            if (focus_search) {
                                focus_search = node_id;
                            }
                        }
                    }
                    if (node.test) {
                        font.background = "lightgrey";
                        shapeProperties = {borderDashes: true};
                    }
                    if (node.recipe == "Platform") {
                        font.background = "Violet";
                    }
                    if (node.vendor) {
                        borderColor = "Red";
                        shapeProperties = {borderDashes: [3,5]};
                        borderWidth = 2;
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
                            let target_id = targets[dep_id] || dep_id;
                            edges.push({id: edge_counter, from: node_id, to: target_id,
                                        color: {color: "SkyBlue", highlight: "Blue"}});
                            global_edges[edge_counter++] = dep;
                        }
                        if (show_transitive && dep.direct === false){
                            let target_id = targets[dep_id] || dep_id;
                            edges.push({id: edge_counter, from: node_id, to: target_id,
                                        color: {color: "LightGray", highlight: "Gray"},
                                        dashes: true});
                            global_edges[edge_counter++] = dep;
                        }
                        if (loop_error && loop_error[1] == node["name"] && loop_error[0] == dep["ref"]) {
                            let target_id = targets[dep_id] || dep_id;
                            edges.push({id: edge_counter, from: node_id, to: target_id,
                                        color: {color: "Red", highlight: "Red"},
                                        smooth: { enabled: true, type: 'curvedCW', roundness: 0.4 },
                                        arrows: "from",
                                        label: "loop",
                                        title: "loop"});
                            global_edges[edge_counter++] = dep;
                        }
                    }
                }
                if (conflict) {
                    let conflict_id = null;
                    if (conflict.branch1.dst_id) { // already created conflict node
                        conflict_id = conflict.branch1.dst_id;
                    }
                    else {
                        conflict_id = "conflict_id";
                        nodes.push({
                            id: conflict_id,
                            font: {color: "white"},
                            label: conflict.name,
                            shape: "circle",
                            color: {background: "black",
                                    highlight: {background: "black", border: "Blue"}},
                        });
                        edges.push({id: edge_counter, from: conflict.branch1.src_id, to: conflict_id,
                                    color: {color: "Red", highlight: "Red"},
                                    label: conflict.branch1.require.ref});
                        global_edges[edge_counter++] = conflict.branch1.require;
                    }
                    edges.push({id: edge_counter, from: conflict.branch2.src_id, to: conflict_id,
                                color: {color: "Red", highlight: "Red"},
                                label: conflict.branch2.require.ref});
                    global_edges[edge_counter++] = conflict.branch2.require;
                }
                if (provide_conflict) {
                    // The nodes are already there, we'll just add an edge to the conflict node
                    edges.push({id: edge_counter,
                                from: provide_conflict.conflicting_node.id,
                                to: provide_conflict.node.id,
                                color: {color: "Red", highlight: "Red"},
                                label: provide_conflict.provided,
                                title: "Both nodes provide the same requirement: " + provide_conflict.provided.join(", "),
                                dashes: true});
                    global_edges[edge_counter++] = {"provided": provide_conflict.provided};
                }
                if(missing_error) {
                    nodes.push({
                        id: "missing_node",
                        font: {multi: 'html', color: "white"},
                        label: missing_error["require"]["ref"],
                        shape: "Circle",
                        color: {background: "Black"},
                    });
                    edges.push({id: edge_counter,
                                from: missing_error["node"]["id"],
                                to: "missing_node",
                                color: {color: "Red", highlight: "Red"},
                                label: "missing",
                                title: "missing",
                                dashes: true});
                    global_edges[edge_counter++] = {"missing": missing_error["error"]};
                }
                return {nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges)};
            };
            function define_legend() {
                let x = 0;
                let y = 0;
                let step = 250;
                let legend_nodes = [];
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
                let counter = 3;
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
                counter++;

                legend_nodes.push({x: x + counter*step, y: y, shape: "box",
                    label: "vendor", font: {size: 35},
                    color: {border: "Red"},
                    shapeProperties: {borderDashes: [3,5]},
                    borderWidth: 2
                });
                return {nodes: new vis.DataSet(legend_nodes)};
            }
            let error = document.getElementById("error");
            if (graph_data["error"]){
                 let div = document.createElement('div');
                 div.innerHTML = "<pre>Error in the graph: " + JSON.stringify(graph_data["error"], undefined, 2) + "</pre>";
                 error.appendChild(div);
            }
            let container = document.getElementById('mynetwork');
            let controls = document.getElementById('controls');
            let legend_container = document.getElementById('mylegend');

            let options = {
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

            let data = define_data();
            let network = new vis.Network(container, data, options);
            let legend_data = define_legend();
            let options_legend = {interaction: {selectable: false, dragView: false, dragNodes: false,
                                                zoomView: false}, physics: {enabled: false}};
            let legend = new vis.Network(legend_container, legend_data, options_legend);

            network.on('click', function (properties) {
                let ids = properties.nodes;
                let ids_edges = properties.edges;
                let control = document.getElementById("details");
                while (control.firstChild) {
                    control.removeChild(control.firstChild);
                }
                if(ids[0] !== undefined || ids_edges[0] !== undefined) {
                    selected = graph_data["nodes"][ids[0]] || global_edges[ids_edges[0]];
                    let div = document.createElement('div');
                    let f = Object.fromEntries(Object.entries(selected).filter(([_, v]) => v != null));
                    div.innerText = JSON.stringify(f, undefined, 2);
                    let div2 = document.createElement('div');
                    div2.innerHTML = "<pre>" + div.innerHTML + "</pre>";
                    control.appendChild(div2);
                    if (show_subgraph && graph_data["nodes"][ids[0]]) {
                        setSubgraphSelectionFromNode(ids[0]);
                    }

                }
                else {
                    control.innerHTML = "Click on one package or edge to show information";
                }
            });
            function draw() {
                let scale = network.getScale();
                let viewPos = network.getViewPosition();
                data = define_data();
                network.setData(data);
                network.redraw();
                network.moveTo({position: viewPos, scale: scale});
                // If we have found a package to focus, we need to move the view
                if (typeof focus_search === "string") {
                    network.focus(focus_search, {animation: true, locked: false});
                }
            }
            function switchBuild() {
                hide_build = !hide_build;
                draw();
            }
            function switchTest() {
                hide_test = !hide_test;
                draw();
            }
            function switchTransitive() {
                show_transitive = !show_transitive;
                draw();
            }
            function collapsePackages() {
                collapse_packages = !collapse_packages;
                draw();
            }
            const debounce = (func, delay) => {
                let timeout;
                return function(...args) {
                    clearTimeout(timeout);
                    timeout = setTimeout(() => func.apply(this, args), delay);
                };
            };
            const debouncedDraw = debounce(draw, 300);
            function searchPackages(e) {
                search_pkgs = e.value;
                debouncedDraw();
            }
            function onSearchKeyDown(event) {
                if (event.key === "Enter") {
                    focus_search = true;
                    draw();
                    focus_search = false;
                }
            }
            function excludePackages(e) {
                excluded_pkgs = e.value;
                debouncedDraw();
            }
            function showPackageType(e) {
                show_package_type = !show_package_type;
                draw();
            }
            function showSubgraph(e) {
                show_subgraph = !show_subgraph;
                draw();
            }
            function showhideclass(id) {
                let elements = document.getElementsByClassName(id)
                for (let i = 0; i < elements.length; i++) {
                    elements[i].style.display = (elements[i].style.display != 'none') ? 'none' : 'block';
                }
            }
            function getNodeLabel(node) {
                let label = null;
                if (node["name"])
                    label =  node["name"] + "/" + node["version"];
                else if (node["ref"])
                    label = node["ref"];
                else
                    label = node.recipe == "Consumer"? "conanfile": "CLI";
                return label;
            }
            function setSubgraphSelectionFromNode(starting_node_id) {
                let node_id_list = [starting_node_id];
                let seen_nodes = [];
                let seen_edges = [];
                while (node_id_list.length > 0) {
                    const node_id = node_id_list.pop();
                    // The node might be hidden
                    if (network.findNode(node_id).length == 0) continue;
                    if (node_id !== undefined && !seen_nodes.includes(node_id)) {
                        const node = graph_data["nodes"][node_id];
                        seen_nodes.push(node_id);
                        for (let dep_id in node["dependencies"]) {
                            // Collapsed dependencies dont have an edge to the matching id, find which
                            if (collapse_packages) {
                                const dep_node = graph_data["nodes"][dep_id];
                                const context = dep_node["context"];
                                const label = getNodeLabel(dep_node);
                                dep_id = collapsed_packages[context][label];
                            }
                            node_id_list.push(dep_id);
                        }
                        const edges = network.getConnectedEdges(node_id);
                        for (let edge_id of edges) {
                            const connectedNodes = network.getConnectedNodes(edge_id);
                            // Only select edges that have a fromId (0th index) equal to current node
                            if (!seen_edges.includes(edge_id) && connectedNodes[0] === node_id) {
                                seen_edges.push(edge_id);
                            }
                        }
                    }
                }
                network.setSelection({nodes: seen_nodes, edges: seen_edges},
                                     {unselectAll: true, highlightEdges: false});
            }
            window.addEventListener("load", () => {
               draw();
            });
        </script>
    </body>
</html>
"""
