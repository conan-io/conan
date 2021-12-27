import json

from conans.assets import templates
from conans.cli.formatters import get_template
from conans.cli.output import ConanOutput, Color
from conans.client.graph.graph import CONTEXT_BUILD, RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_CACHE, \
    BINARY_DOWNLOAD, BINARY_BUILD, BINARY_MISSING, BINARY_UPDATE
from conans.client.installer import build_id


def cli_format_graph_basic(graph):
    # I am excluding the "download"-"cache" or remote information, that is not
    # the definition of the graph, but some history how it was computed
    # maybe we want to summarize that info after the "GraphBuilder" ends?
    # TODO: Should all of this be printed from a json representation of the graph? (the same json
    #   that would be in the json_formatter for the graph?)
    output = ConanOutput()
    requires = {}
    build_requires = {}
    python_requires = {}
    deprecated = {}
    for node in graph.nodes:
        if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
            continue
        if node.context == CONTEXT_BUILD:
            build_requires[node.ref] = node.recipe, node.remote
        else:
            requires[node.ref] = node.recipe, node.remote
        if hasattr(node.conanfile, "python_requires"):
            for r in node.conanfile.python_requires._pyrequires.values():  # TODO: improve interface
                python_requires[r.ref] = r.recipe, r.remote
        if node.conanfile.deprecated:
            deprecated[node.ref] = node.conanfile.deprecated

    output.info("Graph root", Color.BRIGHT_YELLOW)
    path = ": {}".format(graph.root.path) if graph.root.path else ""
    output.info("    {}{}".format(graph.root, path), Color.BRIGHT_CYAN)

    def _format_requires(title, reqs_to_print):
        if not reqs_to_print:
            return
        output.info(title, Color.BRIGHT_YELLOW)
        for ref, (recipe, remote) in sorted(reqs_to_print.items()):
            if remote is not None:
                recipe = "{} ({})".format(recipe, remote.name)
            output.info("    {} - {}".format(ref.repr_notime(), recipe), Color.BRIGHT_CYAN)

    _format_requires("Requirements", requires)
    _format_requires("Build requirements", build_requires)
    _format_requires("Python requires", python_requires)

    def _format_resolved(title, reqs_to_print):
        if not reqs_to_print:
            return
        output.info(title, Color.BRIGHT_YELLOW)
        for k, v in sorted(reqs_to_print.items()):
            output.info("    {}: {}".format(k, v), Color.BRIGHT_CYAN)

    _format_resolved("Resolved alias", graph.aliased)
    _format_resolved("Resolved version ranges", graph.resolved_ranges)

    if deprecated:
        output.info("Deprecated", Color.BRIGHT_YELLOW)
        for d, reason in deprecated.items():
            reason = reason if isinstance(reason, str) else ""
            output.info("    {}{}".format(d, reason), Color.BRIGHT_CYAN)


def cli_format_graph_packages(graph):
    # I am excluding the "download"-"cache" or remote information, that is not
    # the definition of the graph, but some history how it was computed
    # maybe we want to summarize that info after the "GraphBuilder" ends?
    output = ConanOutput()
    requires = {}
    build_requires = {}
    for node in graph.nodes:
        if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
            continue
        if node.context == CONTEXT_BUILD:
            build_requires[node.pref] = node.binary, node.binary_remote
        else:
            requires[node.pref] = node.binary, node.binary_remote

    def _format_requires(title, reqs_to_print):
        if not reqs_to_print:
            return
        output.info(title, Color.BRIGHT_YELLOW)
        for pref, (status, remote) in sorted(reqs_to_print.items(), key=repr):
            if remote is not None:
                status = "{} ({})".format(status, remote.name)
            output.info("    {} - {}".format(pref.repr_notime(), status), Color.BRIGHT_CYAN)

    _format_requires("Requirements", requires)
    _format_requires("Build requirements", build_requires)


class _PrinterGraphItem(object):
    def __init__(self, id, node, is_build_time_node):
        self.id = id
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


class Grapher(object):
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
    graph = Grapher(graph)
    from conans import __version__ as client_version
    return template.render(graph=graph, base_template_path=template_folder, version=client_version)


def graph_html_format(info):
    graph, template_folder = info
    template = get_template(templates.INFO_GRAPH_HTML, template_folder=template_folder)
    return _render_graph(graph, template, template_folder)


def graph_dot_format(info):
    graph, template_folder = info
    template = get_template(templates.INFO_GRAPH_DOT, template_folder=template_folder)
    return _render_graph(graph, template, template_folder)


def graph_json_format(info):
    deps_graph, _ = info
    serialized = deps_graph.serialize()
    json_result = json.dumps(serialized, indent=4)
    return json_result
