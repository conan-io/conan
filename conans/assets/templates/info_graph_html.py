content = """
<html lang="en">
    <head>
        {# For backwards compatibility we prefer local assets over the ones in internet #}
        <script type="text/javascript" src="{{ assets.vis_js|default("https://cdnjs.cloudflare.com/ajax/libs/vis/4.18.1/vis.min.js") }}"></script>
        <link href="{{ assets.vis_css|default("https://cdnjs.cloudflare.com/ajax/libs/vis/4.18.1/vis.min.css") }}" rel="stylesheet" type="text/css"/>
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
            var nodes = new vis.DataSet([
                {%- for node in graph.nodes %}
                    {
                        id: {{ node.id }},
                        label: '{{ node.short_label }}',
                        shape: '{% if node.is_build_requires %}ellipse{% else %}box{% endif %}',
                        color: { background: '{{ graph.binary_color(node) }}'},
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
            ]);
            var edges = new vis.DataSet([
                {%- for src, dst in graph.edges %}
                    { from: {{ src.id }}, to: {{ dst.id }} }{%- if not loop.last %},{% endif %}
                {%- endfor %}
            ]);

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
