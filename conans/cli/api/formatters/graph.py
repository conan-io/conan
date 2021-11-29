from conans.cli.output import ConanOutput, Color
from conans.client.graph.graph import CONTEXT_BUILD, RECIPE_CONSUMER, RECIPE_VIRTUAL


def cli_format_graph_basic(graph):
    # I am excluding the "download"-"cache" or remote information, that is not
    # the definition of the graph, but some history how it was computed
    # maybe we want to summarize that info after the "GraphBuilder" ends?
    output = ConanOutput()
    requires = {}
    build_requires = {}
    python_requires = {}
    for node in graph.nodes:
        if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
            continue
        if node.context == CONTEXT_BUILD:
            build_requires[node.ref] = node.recipe
        else:
            requires[node.ref] = node.recipe
        if hasattr(node.conanfile, "python_requires"):
            for r in node.conanfile.python_requires._pyrequires.values():  # TODO: improve interface
                python_requires[r.ref] = r.recipe

    output.info("Graph root", Color.BRIGHT_YELLOW)
    path = ": {}".format(graph.root.path) if graph.root.path else ""
    output.info("    {}{}".format(graph.root, path), Color.BRIGHT_CYAN)

    def _format_requires(title, reqs_to_print):
        if not reqs_to_print:
            return
        output.info(title, Color.BRIGHT_YELLOW)
        for ref, recipe in sorted(reqs_to_print.items()):
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

    # TODO: missing the version ranges


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
            build_requires[node.pref] = node.binary
        else:
            requires[node.pref] = node.binary

    def _format_requires(title, reqs_to_print):
        if not reqs_to_print:
            return
        output.info(title, Color.BRIGHT_YELLOW)
        for pref, status in sorted(reqs_to_print.items(), key=repr):
            output.info("    {} - {}".format(pref.repr_notime(), status), Color.BRIGHT_CYAN)

    _format_requires("Requirements", requires)
    _format_requires("Build requirements", build_requires)
