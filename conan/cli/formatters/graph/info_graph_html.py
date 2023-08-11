graph_info_html = """
<html lang="en">
    <head>
        <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.18.1/vis.min.js"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.18.1/vis.min.css" rel="stylesheet" type="text/css"/>
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

        <div style="width: 100%;">
            <div id="mynetwork" style="float:left; width: 75%;"></div>
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
            var nodes = [
                {%- for node in graph.nodes %}
                    {% set highlight_node = error is not none and error["should_highlight_node"](node) %}
                    {
                        id: {{ node.id }},
                        label: '{{ node.short_label }}',
                        shape: '{% if highlight_node %}circle{% else %}{% if node.is_build_requires %}ellipse{% else %}box{% endif %}{% endif %}',
                        color: { background: '{% if highlight_node %}red{% else %}{{ graph.binary_color(node) }}{% endif %}'},
                        font: { color: "{% if highlight_node %}white{% else %}black{% endif %}" },
                        fulllabel: '<h3>{{ node.label }}</h3>' +
                                   '<ul>' +
                                   '    <li><b>id</b>: {{ node.package_id }}</li>' +
                                   {%- for key, value in node.data().items() %}
                                   {%- if value %}
                                        {%- if key in ['url', 'homepage'] %}
                                   '    <li><b>{{ key }}</b>: <a href="{{ value }}">{{ value }}</a></li>' +
                                        {%- elif key in ['topics'] %}
                                   '    <li><b>{{ key }}</b>: {{ value|join(", ") }}</li>' +
                                        {%- else %}
                                   '    <li><b>{{ key }}</b>: {{ value }}</li>' +
                                        {%-  endif %}
                                   {%- endif %}
                                   {%- endfor %}
                                   '</ul>'
                    }{%- if not loop.last %},{% endif %}
                {%- endfor %}
            ]
            var edges = [
                {%- for src, dst in graph.edges %}
                    { from: {{ src.id }}, to: {{ dst.id }} }{%- if not loop.last %},{% endif %}
                {%- endfor %}
            ]

            {% if error is not none and error["type"] == "conflict" %}
                // Add error conflict node
                nodes.push({
                    id: "{{ error["type"] }}",
                    label: "{{ error["context"].require.ref }}",
                    shape: "circle",
                    font: { color: "white" },
                    color: "red",
                    fulllabel: '<h3>{{ error["context"].require.ref }}</h3><p>This node creates a conflict in the dependency graph</p>',
                    shapeProperties: { borderDashes: [5, 5] }
                })

                {% if error["context"].node.id is not none %}
                    // Add edge from node that introduces the conflict to the new error node
                    edges.push({from: {{ error["context"].node.id }},
                                to: "{{ error["type"] }}",
                                color: "red",
                                dashes: true,
                                title: "Conflict",
                                physics: false,
                                color: "red",
                                arrows: "to;from"})
                {% endif %}

                {% if error["context"].prev_node is none and error["context"].base_previous.id is not none %}
                    // Add edge from base node to the new error node
                    edges.push({from: {{ error["context"].base_previous.id }},
                                to: "{{ error["type"] }}",
                                color: "red",
                                dashes: true,
                                title: "Conflict",
                                physics: false,
                                color: "red",
                                arrows: "to;from"})
                {% endif %}

                {% if error["context"].prev_node is not none and error["context"].prev_node.id is not none %}
                    // Add edge from previous node that already had conflicting dependency
                    edges.push({from: {{ error["context"].prev_node.id }},
                                to: "{{ error["type"] }}",
                                color: "red",
                                dashes: true,
                                title: "Conflict",
                                physics: false,
                                color: "red",
                                arrows: "to;from"})
                {% endif %}

            {% endif %}

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
            var network = new vis.Network(container, data, options);
            network.on('click', function (properties) {
                var ids = properties.nodes;
                var clickedNodes = nodes.get(ids);
                var control = document.getElementById("details");
                if(clickedNodes[0]) {
                    control.innerHTML = clickedNodes[0].fulllabel;
                }
                else {
                    control.innerHTML = "<b>Package info</b>: No package selected";
                }
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
