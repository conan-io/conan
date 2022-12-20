import json
import os

from jinja2 import Template, select_autoescape


from conan.api.output import cli_out_write
from conan.cli.formatters.graph.info_graph_dot import graph_info_dot
from conan.cli.formatters.graph.info_graph_html import graph_info_html
from conans.client.graph.graph import BINARY_CACHE, \
    BINARY_DOWNLOAD, BINARY_BUILD, BINARY_MISSING, BINARY_UPDATE
from conans.client.installer import build_id
from conans.util.files import load


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

        def ensure_iterable(value):
            if isinstance(value, (list, tuple)):
                return value
            return value,

        return {
            'build_id': build_id(self._conanfile),
            'url': self._conanfile.url,
            'homepage': self._conanfile.homepage,
            'license': self._conanfile.license,
            'author': self._conanfile.author,
            'topics': ensure_iterable(self._conanfile.topics) if self._conanfile.topics else None
        }


class _Grapher(object):
    def __init__(self, deps_graph):
        self._deps_graph = deps_graph
        self.nodes, self.edges = self._build_graph()

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

        return _node_map.values(), edges

    @staticmethod
    def binary_color(node):
        assert isinstance(node, _PrinterGraphItem), "Wrong type '{}'".format(type(node))
        color = {BINARY_CACHE: "SkyBlue",
                 BINARY_DOWNLOAD: "LightGreen",
                 BINARY_BUILD: "Khaki",
                 BINARY_MISSING: "OrangeRed",
                 BINARY_UPDATE: "SeaGreen"}.get(node.binary, "White")
        return color


def _render_graph(graph, template, template_folder):
    graph = _Grapher(graph)
    from conans import __version__ as client_version
    template = Template(template, autoescape=select_autoescape(['html', 'xml']))
    return template.render(graph=graph, base_template_path=template_folder, version=client_version)


def format_graph_html(result):
    graph = result["graph"]
    conan_api = result["conan_api"]
    template_folder = os.path.join(conan_api.cache_folder, "templates")
    user_template = os.path.join(template_folder, "graph.html")
    template = load(user_template) if os.path.isfile(user_template) else graph_info_html
    cli_out_write(_render_graph(graph, template, template_folder))
    if graph.error:
        raise graph.error


def format_graph_dot(result):
    graph = result["graph"]
    conan_api = result["conan_api"]
    template_folder = os.path.join(conan_api.cache_folder, "templates")
    user_template = os.path.join(template_folder, "graph.dot")
    template = load(user_template) if os.path.isfile(user_template) else graph_info_dot
    cli_out_write(_render_graph(graph, template, template_folder))
    if graph.error:
        raise graph.error


def format_graph_json(result):
    graph = result["graph"]
    serialized = graph.serialize()
    json_result = json.dumps(serialized, indent=4)
    cli_out_write(json_result)
    if graph.error:
        raise graph.error
