import json
import os

from jinja2 import Template, select_autoescape

from conan.api.output import cli_out_write, ConanOutput
from conan.cli.formatters.graph.graph_info_text import filter_graph
from conan.cli.formatters.graph.info_graph_dot import graph_info_dot
from conan.cli.formatters.graph.info_graph_html import graph_info_html
from conans.client.graph.graph import BINARY_CACHE, \
    BINARY_DOWNLOAD, BINARY_BUILD, BINARY_MISSING, BINARY_UPDATE
from conans.client.graph.graph_error import GraphConflictError
from conans.client.installer import build_id
from conans.util.files import load


# FIXME: Check all this code when format_graph_[html/dot] use serialized graph

class _PrinterGraphItem(object):
    def __init__(self, _id, node, is_build_time_node):
        self.id = _id
        self._ref = node.ref
        self._conanfile = node.conanfile
        self._is_build_time_node = is_build_time_node
        self.package_id = node.package_id
        self.binary = node.binary

    @property
    def label(self):
        return self._conanfile.display_name

    @property
    def short_label(self):
        if self._ref and self._ref.name:
            return "{}/{}".format(self._ref.name, self._ref.version)
        else:
            return self.label

    @property
    def is_build_requires(self):
        return self._is_build_time_node

    def data(self):
        return {
            'build_id': build_id(self._conanfile),
            'url': self._conanfile.url,
            'homepage': self._conanfile.homepage,
            'license': self._conanfile.license,
            'author': self._conanfile.author,
            'topics': self._conanfile.topics
        }


class _Grapher(object):
    def __init__(self, deps_graph):
        self._deps_graph = deps_graph
        self.node_map, self._edges = self._build_graph()
        self._nodes = self.node_map.values()

    @property
    def nodes(self):
        ConanOutput().warning("--format=html/dot rendering using 'graph' object is deprecated and "
                              "will be removed in future 2.X version. Please upgrade your template "
                              "to use 'deps_graph' instead", warn_tag="deprecated")
        return self._nodes

    @property
    def edges(self):
        ConanOutput().warning("--format=html/dot rendering using 'graph' object is deprecated and "
                              "will be removed in future 2.X version. Please upgrade your template "
                              "to use 'deps_graph' instead", warn_tag="deprecated")
        return self._edges

    def _build_graph(self):
        graph_nodes = self._deps_graph.by_levels()
        build_time_nodes = self._deps_graph.build_time_nodes()
        graph_nodes = reversed([n for level in graph_nodes for n in level])

        _node_map = {}
        for i, node in enumerate(graph_nodes):
            n = _PrinterGraphItem(i, node, bool(node in build_time_nodes))
            _node_map[node] = n

        edges = []
        for node in self._deps_graph.nodes:
            for node_to in node.neighbors():
                src = _node_map[node]
                dst = _node_map[node_to]
                edges.append((src, dst))

        return _node_map, edges

    @staticmethod
    def binary_color(node):
        assert isinstance(node, _PrinterGraphItem), "Wrong type '{}'".format(type(node))
        color = {BINARY_CACHE: "SkyBlue",
                 BINARY_DOWNLOAD: "LightGreen",
                 BINARY_BUILD: "Khaki",
                 BINARY_MISSING: "OrangeRed",
                 BINARY_UPDATE: "SeaGreen"}.get(node.binary, "White")
        return color


def _render_graph(graph, error, template, template_folder):
    deps_graph = graph.serialize()
    graph = _Grapher(graph)
    from conan import __version__
    template = Template(template, autoescape=select_autoescape(['html', 'xml']))
    return template.render(deps_graph=deps_graph, graph=graph, error=error,
                           base_template_path=template_folder, version=__version__)


def format_graph_html(result):
    graph = result["graph"]
    conan_api = result["conan_api"]

    template_folder = os.path.join(conan_api.cache_folder, "templates")
    user_template = os.path.join(template_folder, "graph.html")
    template = load(user_template) if os.path.isfile(user_template) else graph_info_html
    error = {
        "type": "unknown",
        "context": graph.error,
        "should_highlight_node": lambda node: False
    }
    if isinstance(graph.error, GraphConflictError):
        error["type"] = "conflict"
        error["should_highlight_node"] = lambda node: node.id == graph.error.node.id
    cli_out_write(_render_graph(graph, error, template, template_folder))


def format_graph_dot(result):
    graph = result["graph"]
    conan_api = result["conan_api"]

    template_folder = os.path.join(conan_api.cache_folder, "templates")
    user_template = os.path.join(template_folder, "graph.dot")
    template = load(user_template) if os.path.isfile(user_template) else graph_info_dot
    cli_out_write(_render_graph(graph, None, template, template_folder))


def format_graph_json(result):
    graph = result["graph"]
    field_filter = result.get("field_filter")
    package_filter = result.get("package_filter")
    serial = graph.serialize()
    serial = filter_graph(serial, package_filter=package_filter, field_filter=field_filter)
    json_result = json.dumps({"graph": serial}, indent=4)
    cli_out_write(json_result)
