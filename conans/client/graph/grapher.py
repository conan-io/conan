from conans.client.graph.graph import BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_MISSING, \
    BINARY_UPDATE
from conans.client.installer import build_id
from conans.util.files import save
import os


class ConanGrapher(object):
    def __init__(self, deps_graph):
        self._deps_graph = deps_graph

    def graph(self):
        graph_lines = ['digraph {\n']

        for node in self._deps_graph.nodes:
            depends = node.neighbors()
            if depends:
                depends = " ".join('"%s"' % str(d.ref) for d in depends)
                graph_lines.append('    "%s" -> {%s}\n' % (node.conanfile.display_name, depends))

        graph_lines.append('}\n')
        return ''.join(graph_lines)

    def graph_file(self, output_filename):
        save(output_filename, self.graph())


class ConanHTMLGrapher(object):
    def __init__(self, deps_graph, cache_folder):
        self._deps_graph = deps_graph
        self._cache_folder = cache_folder

    def _visjs_paths(self):
        visjs = "https://cdnjs.cloudflare.com/ajax/libs/vis/4.18.1/vis.min.js"
        viscss = "https://cdnjs.cloudflare.com/ajax/libs/vis/4.18.1/vis.min.css"
        visjs_path = os.path.join(self._cache_folder, "vis.min.js")
        visjs = visjs_path if os.path.exists(visjs_path) else visjs
        viscss_path = os.path.join(self._cache_folder, "vis.min.css")
        viscss = viscss_path if os.path.exists(viscss_path) else viscss
        return visjs, viscss

    def graph_file(self, filename):
        save(filename, self.graph())

    def graph(self):
        nodes = []
        nodes_map = {}
        graph_nodes = self._deps_graph.by_levels()
        graph_nodes = reversed([n for level in graph_nodes for n in level])
        for i, node in enumerate(graph_nodes):
            ref, conanfile = node.ref, node.conanfile
            nodes_map[node] = i

            label = "%s/%s" % (ref.name, ref.version) if ref else conanfile.display_name
            fulllabel = ["<h3>%s</h3>" % conanfile.display_name]
            fulllabel.append("<ul>")
            for name, data in [("id", node.package_id),
                               ("build_id", build_id(conanfile)),
                               ("url", '<a href="{url}">{url}</a>'.format(url=conanfile.url)),
                               ("homepage",
                                '<a href="{url}">{url}</a>'.format(url=conanfile.homepage)),
                               ("license", conanfile.license),
                               ("author", conanfile.author),
                               ("topics", str(conanfile.topics))]:
                if data:
                    if isinstance(data, (tuple, list)):
                        data = ', '.join(data)
                    data = data.replace("'", '"')
                    fulllabel.append("<li><b>%s</b>: %s</li>" % (name, data))

            fulllabel.append("<ul>")
            fulllabel = "".join(fulllabel)

            if node.build_require:
                shape = "ellipse"
            else:
                shape = "box"
            color = {BINARY_CACHE: "SkyBlue",
                     BINARY_DOWNLOAD: "LightGreen",
                     BINARY_BUILD: "Khaki",
                     BINARY_MISSING: "OrangeRed",
                     BINARY_UPDATE: "SeaGreen"}.get(node.binary, "White")
            nodes.append("{id: %d, label: '%s', shape: '%s', "
                         "color: {background: '%s'}, fulllabel: '%s'}"
                         % (i, label, shape, color, fulllabel))
        nodes = ",\n".join(nodes)

        edges = []
        for node in self._deps_graph.nodes:
            for node_to in node.neighbors():
                src = nodes_map[node]
                dst = nodes_map[node_to]
                edges.append("{ from: %d, to: %d }" % (src, dst))
        edges = ",\n".join(edges)

        result = self._template.replace("%NODES%", nodes).replace("%EDGES%", edges)
        visjs, viscss = self._visjs_paths()
        return result.replace("%VISJS%", visjs).replace("%VISCSS%", viscss)

    _template = """<html>

<head>
  <script type="text/javascript" src="%VISJS%"></script>
  <link href="%VISCSS%" rel="stylesheet" type="text/css"/>
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
      %NODES%
    ]);
    var edges = new vis.DataSet([
     %EDGES%
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
        arrows: { to: {enabled: true}},
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
                           if(clickedNodes[0])
                              control.innerHTML = clickedNodes[0].fulllabel;
                           else
                              control.innerHTML = "<b>Package info</b>: No package selected";
                         });
  </script>
</body>
</html>
"""
