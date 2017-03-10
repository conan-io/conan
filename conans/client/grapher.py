from conans.util.files import save
from conans.client.installer import build_id


class ConanGrapher(object):
    def __init__(self, project_reference, deps_graph):
        self._deps_graph = deps_graph
        self._project_reference = project_reference

    def graph(self):
        graph_lines = ['digraph {\n']

        for node in self._deps_graph.nodes:
            ref = node.conan_ref or self._project_reference
            depends = self._deps_graph.neighbors(node)
            if depends:
                depends = " ".join('"%s"' % str(d.conan_ref) for d in depends)
                graph_lines.append('    "%s" -> {%s}\n' % (str(ref), depends))

        graph_lines.append('}\n')
        return ''.join(graph_lines)

    def graph_file(self, output_filename):
        save(output_filename, self.graph())


class ConanHTMLGrapher(object):
    def __init__(self, project_reference, deps_graph):
        self._deps_graph = deps_graph
        self._project_reference = project_reference

    def graph_file(self, filename):
        save(filename, self.graph())

    def graph(self):
        nodes = []
        nodes_map = {}
        graph_nodes = self._deps_graph.by_levels()
        graph_nodes = reversed([n for level in graph_nodes for n in level])
        for i, node in enumerate(graph_nodes):
            ref, conanfile = node
            nodes_map[node] = i
            if ref:
                label = "%s/%s" % (ref.name, ref.version)
                fulllabel = [str(ref)]
                fulllabel.append("")
                fulllabel.append("id: %s" % conanfile.info.package_id())
                fulllabel.append("build_id: %s" % build_id(conanfile))
                if conanfile.url:
                    fulllabel.append("url: %s" % conanfile.url)
                if conanfile.license:
                    fulllabel.append("license: %s" % conanfile.license)
                if conanfile.author:
                    fulllabel.append("author: %s" % conanfile.author)
                fulllabel = r"\n".join(fulllabel)
            else:
                fulllabel = label = self._project_reference
            nodes.append("{id: %d, label: '%s', shape: 'box', fulllabel: '%s'}"
                         % (i, label, fulllabel))
        nodes = ",\n".join(nodes)

        edges = []
        for node in self._deps_graph.nodes:
            for node_to in self._deps_graph.neighbors(node):
                src = nodes_map[node]
                dst = nodes_map[node_to]
                edges.append("{ from: %d, to: %d }" % (src, dst))
        edges = ",\n".join(edges)

        return self._template.replace("%NODES%", nodes).replace("%EDGES%", edges)

    _template = """<html>

<head>
  <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.18.1/vis.min.js"></script>
  <link href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.18.1/vis.min.css" rel="stylesheet" type="text/css" />
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
  </style>
  <div align="right">
    <a href="javascript:showhideclass('controls')" class="noPrint">Show/hide controls.</a>
  </div>
  <div id="controls" class="controls"  style="display:none"></div>
  <div id="mynetwork"></div>


  <script type="text/javascript">
    function showhideclass(id) {
      var elements = document.getElementsByClassName(id)
      for (var i = 0; i < elements.length; i++) {
        elements[i].style.display = (elements[i].style.display != 'none') ? 'none' : 'block';
      }
    }
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
        filter: 'layout',
        showButton: false,
        container: controls
      }
    };
    var network = new vis.Network(container, data, options);
    network.on( 'click', function(properties) {
        var ids = properties.nodes;
        var clickedNodes = nodes.get(ids);
       for (var i = 0; i < clickedNodes.length; i++) {
          var temp = clickedNodes[i].fulllabel;
          clickedNodes[i].fulllabel =  clickedNodes[i].label;
          clickedNodes[i].label = temp;
          nodes.update(clickedNodes[i]);
        }
    });
  </script>
</body>
</html>
"""
