from conans.cli.output import ConanOutput, Color
from conans.client.graph.graph import CONTEXT_BUILD, RECIPE_CONSUMER, RECIPE_VIRTUAL


def cli_format_graph_basic(graph):
    # I am excluding the "download"-"cache" or remote information, that is not
    # the definition of the graph, but some history how it was computed
    # maybe we want to summarize that info after the "GraphBuilder" ends?
    output = ConanOutput()
    requires = set()
    build_requires = set()
    python_requires = set()
    for node in graph.nodes:
        if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
            continue
        if node.context == CONTEXT_BUILD:
            build_requires.add(node.ref)
        else:
            requires.add(node.ref)
        if hasattr(node.conanfile, "python_requires"):
            python_requires.update(node.conanfile.python_requires.all_refs())

    output.info("Graph root", Color.BRIGHT_YELLOW)
    path = ": {}".format(graph.root.path) if graph.root.path else ""
    output.info("    {}{}".format(graph.root, path), Color.BRIGHT_CYAN)

    def _format_requires(title, reqs_to_print):
        if not reqs_to_print:
            return
        output.info(title, Color.BRIGHT_YELLOW)
        for r in sorted(reqs_to_print):
            msg = r.repr_notime()
            output.info("    {}".format(msg), Color.BRIGHT_CYAN)

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
