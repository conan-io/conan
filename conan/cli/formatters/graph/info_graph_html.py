graph_info_html = r"""
<!DOCTYPE html>
<html lang="en">
    <head>
        <link rel="icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAMAAAAoLQ9TAAABCFBMVEUAAAA+uf4Ah/2p3PxyvPqNzPkSmP6b0/qTz/mIyPeGx/eIyPeZ0vonpv1qu/ii2fx1wviGx/cFjP0erf+p3PyAxfeAxPcWof6q3PyHyPeKyfgJi/2HzfxCuv4Lk/6p3Pyd2PyGx/cBh/0cqP+Hx/ep3PyGx/dTrvmp3PyGx/cRm/6p3Pya1vyGx/eJyPcGjf0brf+Y0vqp3PwXov6ExvcMlf6p3Pyi2vwap/+FzP2IyPeHyPcPmf4Jkv4Di/16w/gerf8VoP6Ex/hErftft/o8t/4vrv4Ljv2h2Pwsn/xStvtZuvpZtPpNsPpvwvlVsfl0wPh/xPcdrP8Un/40pfwjnPw8qfuLyvgsmPXHAAAANnRSTlMA/sR/BxT+/v7CpjQr/v729fX06ufn59nZ2c/HxMDAp6Wcj46Eg4B8cG9tW1JRUE1FRTYkHRKiySDqAAAAsklEQVQY003P1RqCQBQE4KNid3d3N+quugrYUub7v4ko8sFczfx3A2o8xZoV9FibSYScPeo/qa4TS9czF3C5f9vtCsrs88Wz+3O0MgGoxxASD1eM8GUv4NQQ0icf4g48kRlCsONoAfPaxkri6cExmLHT9BdWS++FEOZtX8w0uM93gmNG67Cd30zKMMJGgyqUQkaItIHq52wa+PMjUDJtxVXIdLQ343J4d0w0jH8H2YJHbR8fvSVyLKSviQAAAABJRU5ErkJggg==">
        <title>conan graph info</title>
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
                background-color: white;
                border: 1px solid #dbe1e8;
                border-radius: 6px;
                padding: 2px 8px;
                font: inherit;
                font-size: 12px;
                cursor: pointer;
            }
            .button:hover { border-color: #6366f1; color: #6366f1; }
            label {
                user-select: none
            }
            body { margin: 0; font: 14px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: #0f172a; }
            [hidden] { display: none !important; }
            #container {
                display: grid;
                --sidebar-width: 340px;
                grid-template-columns: minmax(0, 1fr) var(--sidebar-width);
                grid-template-rows: auto minmax(0, 1fr);
                height: 100vh;
            }
            #mylegend {
                grid-column: 1 / -1;
                display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
                padding: 10px 16px;
                background-color: #f8fafc;
                border-bottom: 1px solid #dbe1e8;
            }
            #logo { height: 30px; margin-right: 10px; }
            .chip { padding: 1px 8px; border: 1.5px solid #64748b; border-radius: 4px; background: white;
                    font: 12px/1.5 ui-monospace, Menlo, Consolas, monospace; white-space: nowrap; }
            .legend-sep { width: 1px; height: 18px; margin: 0 6px; background: #dbe1e8; }
            #fit { position: fixed; right: calc(var(--sidebar-width) + 16px); bottom: 16px; padding: 6px 12px; font-size: 13px; }
            #sidebar {
                background-color: #f8fafc;
                border-left: 1px solid #dbe1e8;
                min-height:100%;
                height:0;
                overflow-y: auto;
                padding: 5px 16px;
            }
            #sidebar > div { margin: 10px 0; }
            #sidebar h3 { margin: 20px 0 8px; font-size: 11px; letter-spacing: .06em; text-transform: uppercase; color: #5b6b80; }
            #sidebar > div > input[type="checkbox"] {
                appearance: none; position: relative; width: 32px; height: 18px; margin: 0 8px 0 0;
                vertical-align: middle; border-radius: 9px; background: #dbe1e8; cursor: pointer;
            }
            #sidebar > div > input[type="checkbox"]::after {
                content: ""; position: absolute; top: 2px; left: 2px; width: 14px; height: 14px;
                border-radius: 50%; background: white; box-shadow: 0 1px 2px rgba(0, 0, 0, .3); transition: transform .15s;
            }
            #sidebar > div > input[type="checkbox"]:checked { background: #6366f1; }
            #sidebar > div > input[type="checkbox"]:checked::after { transform: translateX(14px); }
            input[type="search"] { width: 100%; padding: 7px 10px; border: 1px solid #dbe1e8; border-radius: 8px; font: inherit; outline: none; }
            input[type="search"]:focus { border-color: #6366f1; box-shadow: 0 0 0 3px #eef2ff; }
            summary { cursor: pointer; color: #5b6b80; }
            #controls .vis-configuration-wrapper, #controls .vis-config-item { width: auto; float: none; }  /* vis uses fixed widths */
            #controls .vis-config-range { width: 80px; }
            #controls .vis-config-rangeinput { width: 50px; }
            #controls { overflow: hidden; }
            #details { font-size: 13px; }
            .detail-title { font-weight: 600; font-size: 15px; margin-bottom: 6px; word-break: break-all; }
            #details pre { margin: 8px 0 0; padding: 8px; overflow: auto; background: white; border: 1px solid #dbe1e8; border-radius: 6px; }
            .kv { display: grid; grid-template-columns: fit-content(45%) minmax(0, 1fr); column-gap: 10px; margin-top: 8px; }
            .kv > span, .kv > details { padding: 4px 0; border-bottom: 1px solid #dbe1e8; }
            .kv > details { grid-column: 1 / -1; }
            .kv .key, .kv .none { color: #5b6b80; overflow-wrap: break-word; }
            .kv .value { font: 12px/1.6 ui-monospace, Menlo, Consolas, monospace; white-space: pre-line; overflow-wrap: anywhere; }
            .kv summary { color: #0f172a; }
            .kv summary::after { content: " (" attr(data-count) ")"; color: #5b6b80; }
            .kv .kv { margin: 4px 0 2px 5px; padding-left: 10px; border-left: 2px solid #dbe1e8; }
            .kv .kv > span, .kv .kv > details { padding: 2px 0; border-bottom: none; }
            #error:not(:empty) { border: 1px solid #dc2626; background: #fef2f2; border-radius: 8px; padding: 8px 12px; }
            #error strong { color: #dc2626; }
            #error .button { display: block; margin-top: 6px; }
        </style>

        <div id="container">
            <div id="mylegend">
                <svg id="logo" viewBox="368 0 266 264" xmlns="http://www.w3.org/2000/svg">
                    <path d="M501 263.003L369.331 189.647L369 73.1022L500.602 146.459L500.934 263.003H501Z" fill="url(#conan-logo-gradient)"/>
                    <path d="M500.67 146.458L369.068 73.1021L501.067 0L632.67 73.3562L500.67 146.458Z" fill="#86C7F7"/>
                    <path fill-rule="evenodd" clip-rule="evenodd" d="M503.717 39.7583L496.101 40.584L494.975 41.0286H493.782L492.723 41.4733L486.762 42.807L485.901 43.188H485.106L484.377 43.7596L473.383 47.6973L472.853 48.1419C467.886 49.9838 463.846 52.5878 459.541 54.7472L459.077 55.2552C455.169 57.3511 453.845 58.431 451.129 60.9715L450.467 61.4159L447.751 64.9092L447.221 65.3538L446.294 67.1321L445.831 67.6401C442.718 74.4359 442.784 75.5156 443.446 83.4545L443.976 84.2802V85.1059L444.374 85.8045L445.367 88.2815L445.831 88.8531L446.294 90.1234L446.824 90.5678C448.414 93.2989 450.334 95.4584 452.255 97.4272C453.315 98.5705 457.819 102.064 459.607 102.953L460.07 103.461C463.713 105.112 466.362 107.208 470.932 108.732L471.528 109.113L480.404 111.781L481.397 112.225C484.444 112.543 487.689 113.432 491.067 113.813C494.776 114.258 496.763 112.543 499.809 111.273L500.406 110.828H500.803L501.399 110.384L515.506 104.159L516.103 103.715H516.5L517.096 103.27L525.242 99.5866L524.514 99.2691C519.745 99.0786 514.116 99.7772 508.949 99.6502C503.783 99.5232 498.948 98.6339 494.246 98.3799L493.253 97.9352C489.808 97.6177 486.364 96.2205 483.45 95.2679L482.788 94.8868C478.019 93.2355 473.648 89.6153 471.528 85.9316C468.283 79.9615 470.27 75.5791 472.787 70.5616L473.317 70.1172L473.78 69.2915L474.31 68.8469C476.893 65.3537 483.119 60.5267 489.345 58.6214L490.007 58.2403L496.564 56.462L497.491 56.0175H498.485L499.478 55.5729L503.85 55.1919C504.909 54.5567 505.439 54.6203 506.963 54.6203H517.096C518.686 54.6203 520.076 54.6202 521.202 55.1919L527.097 55.954L527.825 56.462C531.402 56.9701 534.383 58.8755 537.429 59.9553L537.959 60.3997L539.813 61.2254L540.277 61.7336C543.456 63.3214 549.086 68.2753 550.278 72.213L550.676 72.8482C552 77.294 551.669 78.7547 550.676 83.1371L550.278 83.9627L548.622 87.3922L551.073 86.4396L551.603 85.9952L571.141 76.3412L571.671 75.8966L576.307 73.6738L576.837 73.2292L581.473 71.0063L582.003 70.4983C582.202 69.5456 576.175 64.782 574.85 63.5753L574.386 62.9403C572.797 61.6701 570.545 59.7646 568.69 58.6849L568.227 58.1769C566.372 57.1607 564.783 55.5729 562.995 54.7472L562.531 54.2392L557.828 51.6352L557.365 51.127L551.205 48.0786L550.609 47.6339L542.728 44.5217L542.065 44.1407L537.297 42.8705L536.568 42.3623H535.707L534.78 41.9813H533.919L533.058 41.4733C529.15 41.0922 524.911 39.8855 520.54 39.5044C515.308 39.0598 510.208 39.6314 505.505 39.2503L503.651 39.6949L503.717 39.7583Z" fill="url(#conan-logo-gradient)"/>
                    <path d="M500.669 146.459L501 263.004L564.383 227.945V111.147L500.669 146.459Z" fill="#A9DCFC"/>
                    <path d="M633 189.964L632.669 73.3563L569.285 108.478V225.213L633 189.964Z" fill="#A9DCFC"/>
                    <path d="M569.285 108.479L564.384 111.146V227.944L569.285 225.213V108.479Z" fill="url(#conan-logo-gradient)"/>
                    <defs><linearGradient id="conan-logo-gradient"><stop stop-color="#0086FD"/><stop offset="1" stop-color="#21AFFF"/></linearGradient></defs>
                </svg>
            </div>
            <div id="mynetwork"></div>
            <button id="fit" class="button noPrint" onclick="network.fit({animation: true})">Fit to screen</button>
            <div id="sidebar">
                <div id="error" class="noPrint"></div>
                <h3>Controls</h3>
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
                    <label for="show_subgraph">Show subgraph</label>
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
                    </div>
                </div>
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
            let color_map = {Cache: "#7dd3fc",
                             Download: "#86efac",
                             Build: "#fde047",
                             Missing: "#fb923c",
                             Update: "#34d399",
                             Skip: "White",
                             Editable: "#cffafe",
                             EditableBuild: "#22d3ee",
                             Invalid: "#f87171",
                             Platform: "#e879f9"};
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
                    borderColor = "#64748b";
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
                        shapeProperties = {borderDashes: true};
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
                                highlight: {background: color, border: "#6366f1"}},
                    });
                }
                for (const [node_id, node] of Object.entries(graph_data["nodes"])) {
                    for (const [dep_id, dep] of Object.entries(node["dependencies"])) {
                        if (dep.direct){
                            let target_id = targets[dep_id] || dep_id;
                            edges.push({id: edge_counter, from: node_id, to: target_id,
                                        color: {color: "#7c8aa0", highlight: "#6366f1"}});
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
                                    highlight: {background: "black", border: "#6366f1"}},
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
                const item = (label, style) => `<span class="chip" style="${style || ''}">${label}</span>`;
                let html = item("require") + item("tool-require", "border-radius: 9px") +
                           item("test-require", "border-radius: 9px; border-style: dashed") +
                           item("vendor", "border: 1.5px dashed Red") + '<span class="legend-sep"></span>';
                for (const [status, color] of Object.entries(color_map)) {
                    html += item(status, `background: ${color}`);
                }
                html += item("Conflict", "border-radius: 9px; background: Black; color: white");
                document.getElementById('mylegend').insertAdjacentHTML("beforeend", html);
            }
            const isEmpty = (v) => v === null || v === "" || (typeof v === "object" && Object.keys(v).length === 0);
            const isComplex = (v) => typeof v === "object" && !isEmpty(v) &&
                                     !(Array.isArray(v) && v.every(x => typeof x !== "object" || x === null));
            function renderEntries(obj, depth = 0) {
                // Render a (nested) object as a key/value grid, with collapsible sub-sections
                const kv = document.createElement('div');
                kv.className = "kv";
                for (const [key, value] of Object.entries(obj)) {
                    if (isComplex(value)) {
                        const section = document.createElement('details');
                        section.open = depth == 0 && JSON.stringify(value).length < 400;
                        const summary = document.createElement('summary');
                        // dependencies are indexed by node id, show their reference instead
                        summary.textContent = /^\d+$/.test(key) && value.ref ? value.ref : key;
                        summary.dataset.count = Object.keys(value).length;
                        section.append(summary, renderEntries(value, depth + 1));
                        kv.append(section);
                        continue;
                    }
                    const k = document.createElement('span');
                    k.className = "key";
                    k.textContent = key;
                    const v = document.createElement('span');
                    v.className = isEmpty(value) ? "value none" : "value";
                    v.textContent = isEmpty(value) ? "-" : Array.isArray(value) ? value.join("\n") : String(value);
                    kv.append(k, v);
                }
                return kv;
            }
            function showDetails(title, obj) {
                const control = document.getElementById("details");
                control.innerHTML = obj ? "" : "Click on one package or edge to show information";
                if (!obj) return;
                const name = document.createElement('div');
                name.className = "detail-title";
                name.textContent = title;
                const formatted = renderEntries(obj);
                const raw = document.createElement('pre');
                raw.textContent = JSON.stringify(obj, undefined, 2);
                raw.hidden = true;
                const toggle = document.createElement('button');
                toggle.className = "button";
                toggle.textContent = "Raw JSON";
                toggle.onclick = () => {
                    raw.hidden = !raw.hidden;
                    formatted.hidden = !raw.hidden;
                    toggle.textContent = raw.hidden ? "Raw JSON" : "Formatted";
                };
                const copy = toggle.cloneNode();
                copy.textContent = "Copy";
                copy.onclick = () => navigator.clipboard.writeText(raw.textContent).then(
                    () => copy.textContent = "Copied!",
                    () => copy.textContent = "Copy failed"
                ).finally(() => setTimeout(() => copy.textContent = "Copy", 1500));
                control.append(name, toggle, " ", copy, formatted, raw);
            }
            showDetails();
            define_legend();
            if (graph_data["error"]) {
                const error = graph_data["error"];
                const label = (id) => graph_data["nodes"][id] ? getNodeLabel(graph_data["nodes"][id]) : id;
                const messages = {  // [message, node to focus]
                    conflict: () => [`Version conflict: ${error.branch2.require.ref} required by ${label(error.branch2.src_id)} ` +
                                     `conflicts with ${error.branch1.require.ref} required by ${label(error.branch1.src_id)}`,
                                     error.branch1.dst_id || "conflict_id"],
                    provide_conflict: () => [`Provide conflict: ${label(error.node.id)} and ${label(error.conflicting_node.id)} ` +
                                             `both provide ${error.provided.join(", ")}`, error.node.id],
                    missing: () => [`Package ${error.require.ref} required by ${label(error.node.id)} not resolved: ${error.error}`,
                                    "missing_node"],
                    loop: () => [`Loop in the graph: ${label(error.node.id)} requires ${error.require.ref}, ` +
                                 `which is already one of its ancestors`, error.node.id],
                };
                const [message, node_id] = messages[error.type] ? messages[error.type]() : [error.type, null];
                const box = document.getElementById("error");
                box.innerHTML = "<strong>Error:</strong> ";
                box.append(message);
                if (node_id) {
                    const show = document.createElement('button');
                    show.className = "button";
                    show.textContent = "Show in graph";
                    show.onclick = () => {
                        if (network.findNode(node_id).length == 0) return;  // hidden by the filters
                        network.selectNodes([node_id]);
                        network.focus(node_id, {scale: 1, animation: true});
                    };
                    box.append(show);
                }
            }
            let container = document.getElementById('mynetwork');
            let controls = document.getElementById('controls');

            let options = {
                autoResize: true,
                locale: 'en',
                edges: {
                    arrows: { to: {enabled: true, scaleFactor: 0.6} },
                    smooth: { enabled: false}
                },
                nodes: {font: {'face': 'ui-monospace, Menlo, Consolas, monospace', 'align': 'left', 'color': "#0f172a"},
                        margin: {top: 8, bottom: 8, left: 12, right: 12}, shapeProperties: {borderRadius: 6}},
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
            // With "DU" direction vis stores levelSeparation as negative, show the real value in the slider
            const getConfigValue = network.configurator._getValue.bind(network.configurator);
            network.configurator._getValue = (path) => path.at(-1) === "levelSeparation" ?
                Math.abs(getConfigValue(path)) : getConfigValue(path);
            network.setOptions({configure: options.configure});

            network.on('click', function (properties) {
                let ids = properties.nodes;
                let ids_edges = properties.edges;
                if (graph_data["nodes"][ids[0]]) {
                    showDetails(getNodeLabel(graph_data["nodes"][ids[0]]), graph_data["nodes"][ids[0]]);
                    if (show_subgraph) {
                        setSubgraphSelectionFromNode(ids[0]);
                    }
                } else if (global_edges[ids_edges[0]]) {
                    const edge = data.edges.get(ids_edges[0]);
                    const src = graph_data["nodes"][edge.from];
                    showDetails((src ? getNodeLabel(src) : edge.from) + " \u2192 " +
                                (global_edges[ids_edges[0]].ref || edge.to), global_edges[ids_edges[0]]);
                } else {
                    showDetails();
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
