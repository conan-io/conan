from collections import OrderedDict


from conans.client.graph.graph import BINARY_SKIP, RECIPE_CONSUMER, RECIPE_VIRTUAL,\
    RECIPE_EDITABLE
from conans.cli.output import Color, ConanOutput
from conans.model.package_ref import PkgReference


def _get_python_requires(conanfile):
    result = set()
    python_requires = getattr(conanfile, "python_requires", None)
    if python_requires:
        result.update(conanfile.python_requires.all_refs())
    return result


def _print_deprecated(deps_graph):
    out = ConanOutput()
    deprecated = {}
    for node in deps_graph.nodes:
        if node.conanfile.deprecated:
            deprecated[node.ref] = node.conanfile.deprecated

    if deprecated:
        out.info("Deprecated", Color.BRIGHT_YELLOW)
        for d, reason in deprecated.items():
            reason = " in favor of '{}'".format(reason) if isinstance(reason, str) else ""
            out.info("    {}{}".format(d, reason), Color.BRIGHT_CYAN)


def print_graph(deps_graph):
    out = ConanOutput()
    requires = OrderedDict()
    build_requires = OrderedDict()
    python_requires = set()
    build_time_nodes = deps_graph.build_time_nodes()
    for node in sorted(deps_graph.nodes):
        python_requires.update(_get_python_requires(node.conanfile))
        if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL):
            continue
        pref = PkgReference(node.ref, node.package_id)
        if node in build_time_nodes:  # TODO: May use build_require_context information
            build_requires.setdefault(pref, []).append(node)
        else:
            requires.setdefault(pref, []).append(node)

    out.info("Requirements", Color.BRIGHT_YELLOW)

    def _recipes(nodes):
        for _, list_nodes in nodes.items():
            node = list_nodes[0]  # For printing recipes, we can use the first one
            if node.recipe == RECIPE_EDITABLE:
                from_text = "from user folder"
            else:
                from_text = ("from local cache" if not node.remote
                             else "from '%s'" % node.remote.name)
            out.info("    %s %s - %s" % (str(node.ref), from_text, node.recipe),
                        Color.BRIGHT_CYAN)

    _recipes(requires)
    if python_requires:
        out.info("Python requires", Color.BRIGHT_YELLOW)
        for p in python_requires:
            out.info("    %s" % repr(p.copy_clear_rev()), Color.BRIGHT_CYAN)
    out.info("Packages", Color.BRIGHT_YELLOW)

    def _packages(nodes):
        for package_id, list_nodes in nodes.items():
            # The only way to have more than 1 states is to have 2
            # and one is BINARY_SKIP (privates)
            binary = set(n.binary for n in list_nodes)
            if len(binary) > 1:
                binary.remove(BINARY_SKIP)
            assert len(binary) == 1
            binary = binary.pop()
            out.info("    %s - %s" % (str(package_id), binary), Color.BRIGHT_CYAN)
    _packages(requires)

    if build_requires:
        out.info("Build requirements", Color.BRIGHT_YELLOW)
        _recipes(build_requires)
        out.info("Build requirements packages", Color.BRIGHT_YELLOW)
        _packages(build_requires)

    _print_deprecated(deps_graph)

    out.writeln("")
