from conans.client.output import Color
from conans.model.ref import PackageReference
from conans.model.workspace import WORKSPACE_FILE
from collections import OrderedDict
from conans.client.graph.graph import BINARY_SKIP


def print_graph(deps_graph, out):
    requires = OrderedDict()
    build_requires = OrderedDict()
    python_requires = set()
    for node in sorted(deps_graph.nodes):
        python_requires.update(getattr(node.conanfile, "python_requires", []))
        if not node.conan_ref:
            continue
        package_id = PackageReference(node.conan_ref, node.conanfile.info.package_id())
        if node.build_require:
            build_requires.setdefault(package_id, []).append(node)
        else:
            requires.setdefault(package_id, []).append(node)

    out.writeln("Requirements", Color.BRIGHT_YELLOW)

    def _recipes(nodes):
        for package_id, list_nodes in nodes.items():
            node = list_nodes[0]  # For printing recipes, we can use the first one
            if node.remote == WORKSPACE_FILE:
                from_text = "from '%s'" % WORKSPACE_FILE
            else:
                from_text = "from local cache" if not node.remote else "from '%s'" % node.remote.name
            out.writeln("    %s %s - %s" % (repr(node.conan_ref), from_text, node.recipe), Color.BRIGHT_CYAN)

    _recipes(requires)
    if python_requires:
        out.writeln("Python requires", Color.BRIGHT_YELLOW)
        for p in python_requires:
            out.writeln("    %s" % repr(p), Color.BRIGHT_CYAN)
    out.writeln("Packages", Color.BRIGHT_YELLOW)

    def _packages(nodes):
        for package_id, list_nodes in nodes.items():
            # The only way to have more than 1 states is to have 2
            # and one is BINARY_SKIP (privates)
            binary = set(n.binary for n in list_nodes)
            if len(binary) > 1:
                binary.remove(BINARY_SKIP)
            assert len(binary) == 1
            binary = binary.pop()
            out.writeln("    %s - %s" % (repr(package_id), binary), Color.BRIGHT_CYAN)
    _packages(requires)

    if build_requires:
        out.writeln("Build requirements", Color.BRIGHT_YELLOW)
        _recipes(build_requires)
        out.writeln("Build requirements packages", Color.BRIGHT_YELLOW)
        _packages(build_requires)

    out.writeln("")
