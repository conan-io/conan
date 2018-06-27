from conans.client.output import Color
from conans.model.ref import PackageReference
from conans.model.workspace import WORKSPACE_FILE


def print_graph(deps_graph, out):
    all_nodes = []
    ids = set()
    for node in sorted(n for n in deps_graph.nodes if n.conan_ref):
        package_id = PackageReference(node.conan_ref, node.conanfile.info.package_id())
        if package_id not in ids:
            all_nodes.append(node)
            ids.add(package_id)
    requires = [n for n in all_nodes if not n.build_require]
    out.writeln("Requirements", Color.BRIGHT_YELLOW)

    def _recipes(nodes):
        for node in nodes:
            if node.remote == WORKSPACE_FILE:
                from_text = "from '%s'" % WORKSPACE_FILE
            else:
                from_text = "from local cache" if not node.remote else "from '%s'" % node.remote.name
            out.writeln("    %s %s - %s" % (repr(node.conan_ref), from_text, node.recipe), Color.BRIGHT_CYAN)

    _recipes(requires)
    out.writeln("Packages", Color.BRIGHT_YELLOW)

    def _packages(nodes):
        for node in nodes:
            ref, conanfile = node.conan_ref, node.conanfile
            ref = PackageReference(ref, conanfile.info.package_id())
            out.writeln("    %s - %s" % (repr(ref), node.binary), Color.BRIGHT_CYAN)
    _packages(requires)

    build_requires = [n for n in all_nodes if n.build_require]
    if build_requires:
        out.writeln("Build requirements", Color.BRIGHT_YELLOW)
        _recipes(build_requires)
        out.writeln("Build requirements packages", Color.BRIGHT_YELLOW)
        _packages(build_requires)

    out.writeln("")
