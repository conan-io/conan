import os
import re
from collections import OrderedDict
from conans.client.graph.graph import BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_MISSING, \
    BINARY_UPDATE
from conans.client.installer import build_id
from conans.util.files import save
from conans.errors import ConanException


class ConanGrapher(object):

    def __init__(self, deps_graph):
        """
        Object to write the Conan dependency graph into a Graphviz Dot file
        (https://www.graphviz.org/doc/info/lang.html)

        :param deps_graph: Conan built-in Dependency Graph
        """
        self._deps_graph = deps_graph

    def graph(self):
        """
        Creates the Dot file content.

        :return: String with a content of the Dot file for the defined deps_graph.
        """
        dot_graph = ['strict digraph {']
        dot_graph.append(self._dot_configuration)
        dot_graph.append('\n')

        # First, create the nodes
        nodes = self._add_single_nodes_to_graph(dot_graph)

        # Then, the adjacency matrix
        self._add_adjacency_matrix(nodes, dot_graph)

        dot_graph.append('}\n')

        return ''.join(dot_graph)

    def graph_file(self, output_filename):
        """
        Writes the defined deps_graph tree into a Dot file.

        :param output_filename: filename of the output Dot file.
        """
        save(output_filename, self.graph())

    def _add_single_nodes_to_graph(self, dot_graph):
        """
        Creates a nodes representation with all the fields to be displayed in the Dot file and
        fills-in the nodes of the Dot graph (dot_graph) with this information.

        :param dot_graph: String containing the DOT file structure (the Dot configuration)
        :return: A Map of nodes identified by its display_name with all the useful fields.
        """
        # Store list of build_requires nodes
        build_time_nodes = self._deps_graph.build_time_nodes()

        # Store the root node
        root_node = self._deps_graph.root
        if root_node.conanfile.name and root_node.conanfile.version:
            root_id = "{}/{}".format(root_node.conanfile.name, root_node.conanfile.version)
        elif root_node.conanfile.name:
            root_id = root_node.conanfile.name
        else:
            root_id = root_node.conanfile.display_name

        # Store nodes in ordered dict, for deterministic output to dot file
        nodes = {}

        # First, gather the nodes info
        for node in self._deps_graph.nodes:
            if node.conanfile.name and node.conanfile.version:
                node_name = node.conanfile.name
                node_version = node.conanfile.version
            elif node.conanfile.name:
                node_name = node.conanfile.name
                node_version = ""
            else:
                node_name = node.conanfile.display_name
                node_version = ""

            node_id = node.conanfile.display_name

            try:
                node_user = node.conanfile.user
            except ConanException:
                node_user = ""

            try:
                node_channel = node.conanfile.channel
            except ConanException:
                node_channel = ""

            nodes[node_id] = {
                "node": node,
                "name": node_name,
                "version": node_version,
                "user": node_user,
                "channel": node_channel,
                "is_root": node_id == root_id,
                "build_requires": node in build_time_nodes
            }

        # Then iterate over the ordered set of nodes & write to dot graph
        for id in sorted(nodes.keys()):
            if nodes[id]['version'] and nodes[id]['user'] and nodes[id]['channel']:
                dot_node = self._dot_node_template_with_user_channel \
                    .replace("%NODE_NAME%", nodes[id]['name']) \
                    .replace("%NODE_VERSION%", nodes[id]['version']) \
                    .replace("%NODE_USER%", nodes[id]['user']) \
                    .replace("%NODE_CHANNEL%", nodes[id]['channel'])
            elif nodes[id]['version']:
                dot_node = self._dot_node_template.replace("%NODE_NAME%", nodes[id]['name']) \
                    .replace("%NODE_VERSION%", nodes[id]['version'])
            else:
                dot_node = self._dot_node_template_without_version_user_channel \
                    .replace("%NODE_NAME%", nodes[id]['name'])
            # Color the nodes
            if nodes[id]['is_root']:
                dot_node = self._dot_node_colors_template_root_node + dot_node
            elif nodes[id]['build_requires']:
                # TODO: May use build_require_context information
                dot_node = self._dot_node_colors_template_build_requires + dot_node
            else:  # requires
                dot_node = self._dot_node_colors_template_requires + dot_node

            # Add single node to graph
            dot_graph.append('    "{}" {}\n'.format(
                id,
                dot_node
            ))

        return nodes

    def _add_adjacency_matrix(self, nodes, dot_graph):
        """
        Fills in the adjancency matrix into the dot_graph string in the following form
            "node_id" -> {"dep_1_id" "dep_2_id" ... "dep_n_id"}

        :param nodes: A Map of nodes identified by its display_name with all the useful fields.
        :param dot_graph: String containing the DOT file structure (the DOT configuration and nodes)
        """
        for id in sorted(nodes.keys()):
            depends = nodes[id]['node'].neighbors()
            if depends:
                deps_links = ""
                for dep_node in depends:
                    dep_node_id = dep_node.conanfile.display_name
                    deps_links += ' "%s"' % dep_node_id

                # Add nodes to matrix
                dot_graph.append('    "{}" -> {{{}}}\n'.format(
                    id,
                    deps_links
                ))

    _dot_configuration = """
    graph [
      bgcolor = white,
      style = "filled",
      rankdir = TD,
      splines = ortho,
      ranksep = 1,
      nodesep = 0.7
    ];
    node [
      style = "filled",
      fontname = "Helvetica",
      fontsize = "18",
      shape=rect
    ];
    edge [
      style = solid
    ];"""
    _dot_node_colors_template_root_node = """[ fillcolor=mintcream, color=limegreen """
    _dot_node_colors_template_build_requires = """[ fillcolor=lightyellow, color=gold """
    _dot_node_colors_template_requires = """[ fillcolor=azure, color=dodgerblue """
    _dot_node_template_without_version_user_channel = """ label=<
     <table border="0" cellborder="0" cellspacing="0">
       <tr><td align="center"><b>%NODE_NAME%</b></td></tr>
     </table>>];"""
    _dot_node_template_with_user_channel = """ label=<
     <table border="0" cellborder="0" cellspacing="0">
       <tr><td align="center"><b>%NODE_NAME%</b></td></tr>
       <tr><td align="center"><font point-size="12">%NODE_VERSION%</font></td></tr>
       <tr><td align="center"><i><font point-size="12">%NODE_USER%/%NODE_CHANNEL%</font></i></td></tr>
     </table>>];"""
    _dot_node_template = """ label=<
     <table border="0" cellborder="0" cellspacing="0">
       <tr><td align="left"><b>%NODE_NAME%</b></td></tr>
       <tr><td align="center"><font point-size="12">%NODE_VERSION%</font></td></tr>
     </table>>];"""


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
        build_time_nodes = self._deps_graph.build_time_nodes()
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

            if node in build_time_nodes:  # TODO: May use build_require_context information
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
