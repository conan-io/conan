from conan.api.output import ConanOutput, Color
from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_VIRTUAL, CONTEXT_BUILD


def print_graph_basic(graph):
    # I am excluding the "download"-"cache" or remote information, that is not
    # the definition of the graph, but some history how it was computed
    # maybe we want to summarize that info after the "GraphBuilder" ends?
    # TODO: Should all of this be printed from a json representation of the graph? (the same json
    #   that would be in the json_formatter for the graph?)
    output = ConanOutput()
    requires = {}
    build_requires = {}
    test_requires = {}
    python_requires = {}
    deprecated = {}
    for node in graph.nodes:
        if hasattr(node.conanfile, "python_requires"):
            for r in node.conanfile.python_requires._pyrequires.values():  # TODO: improve interface
                python_requires[r.ref] = r.recipe, r.remote
        if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
            continue
        if node.context == CONTEXT_BUILD:
            build_requires[node.ref] = node.recipe, node.remote
        else:
            if node.test:
                test_requires[node.ref] = node.recipe, node.remote
            else:
                requires[node.ref] = node.recipe, node.remote
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
    _format_requires("Test requirements", test_requires)
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
            reason = f": {reason}" if reason else ""
            output.info("    {}{}".format(d, reason), Color.BRIGHT_CYAN)

    if graph.error:
        output.info("Graph error", Color.BRIGHT_RED)
        output.info("    {}".format(graph.error), Color.BRIGHT_RED)


def print_graph_packages(graph):
    # I am excluding the "download"-"cache" or remote information, that is not
    # the definition of the graph, but some history how it was computed
    # maybe we want to summarize that info after the "GraphBuilder" ends?
    output = ConanOutput()
    requires = {}
    build_requires = {}
    test_requires = {}
    for node in graph.nodes:
        if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
            continue
        if node.context == CONTEXT_BUILD:
            build_requires[node.pref] = node.binary, node.binary_remote
        else:
            if node.test:
                test_requires[node.pref] = node.binary, node.binary_remote
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
    _format_requires("Test requirements", test_requires)
    _format_requires("Build requirements", build_requires)
