import fnmatch

from collections import OrderedDict

from conans.paths import SimplePaths
from conans.client.output import Color
from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference
from conans.client.installer import build_id


class Printer(object):
    """ Print some specific information """

    INDENT_COLOR = {0: Color.BRIGHT_CYAN,
                    1: Color.BRIGHT_RED,
                    2: Color.BRIGHT_GREEN,
                    3: Color.BRIGHT_YELLOW,
                    4: Color.BRIGHT_MAGENTA}

    INDENT_SPACES = 4

    def __init__(self, out):
        self._out = out

    def print_inspect(self, inspect):
        for k, v in inspect.items():
            if isinstance(v, dict):
                self._out.writeln("%s" % k)
                for sk, sv in sorted(v.items()):
                    self._out.writeln("    %s: %s" % (sk, str(sv)))
            else:
                self._out.writeln("%s: %s" % (k, str(v)))

    def _print_paths(self, ref, conan, path_resolver, show):
        if isinstance(ref, ConanFileReference):
            if show("export_folder"):
                path = path_resolver.export(ref)
                self._out.writeln("    export_folder: %s" % path, Color.BRIGHT_GREEN)
            if show("source_folder"):
                path = path_resolver.source(ref, conan.short_paths)
                self._out.writeln("    source_folder: %s" % path, Color.BRIGHT_GREEN)
            if show("build_folder") and isinstance(path_resolver, SimplePaths):
                # @todo: check if this is correct or if it must always be package_id()
                bid = build_id(conan)
                if not bid:
                    bid = conan.info.package_id()
                path = path_resolver.build(PackageReference(ref, bid), conan.short_paths)
                self._out.writeln("    build_folder: %s" % path, Color.BRIGHT_GREEN)
            if show("package_folder") and isinstance(path_resolver, SimplePaths):
                id_ = conan.info.package_id()
                path = path_resolver.package(PackageReference(ref, id_), conan.short_paths)
                self._out.writeln("    package_folder: %s" % path, Color.BRIGHT_GREEN)

    def print_info(self, deps_graph, _info, registry, node_times=None, path_resolver=None, package_filter=None,
                   show_paths=False):
        """ Print the dependency information for a conan file

            Attributes:
                deps_graph: the dependency graph of conan file references to print
                placeholder_reference: the conan file reference that represents the conan
                                       file for a project on the path. This may be None,
                                       in which case the project itself will not be part
                                       of the printed dependencies.
        """
        if _info is None:  # No filter
            def show(_):
                return True
        else:
            _info_lower = [s.lower() for s in _info]

            def show(field):
                return field in _info_lower

        compact_nodes = OrderedDict()
        for node in sorted(deps_graph.nodes):
            compact_nodes.setdefault((node.conan_ref, node.conanfile.info.package_id()), []).append(node)

        for (ref, package_id), list_nodes in compact_nodes.items():
            node = list_nodes[0]
            conan = node.conanfile
            if not ref:
                # ref is only None iff info is being printed for a project directory, and
                # not a passed in reference
                if conan.output is None:  # Identification of "virtual" node
                    continue
                ref = str(conan)
            if package_filter and not fnmatch.fnmatch(str(ref), package_filter):
                continue

            self._out.writeln("%s" % str(ref), Color.BRIGHT_CYAN)
            try:
                # Excludes PROJECT fake reference
                reg_remote = registry.get_recipe_remote(ref)
            except:
                reg_remote = None

            if show("id"):
                self._out.writeln("    ID: %s" % package_id, Color.BRIGHT_GREEN)
            if show("build_id"):
                bid = build_id(conan)
                self._out.writeln("    BuildID: %s" % bid, Color.BRIGHT_GREEN)

            if show_paths:
                self._print_paths(ref, conan, path_resolver, show)

            if isinstance(ref, ConanFileReference) and show("remote"):
                if reg_remote:
                    self._out.writeln("    Remote: %s=%s" % (reg_remote.name, reg_remote.url),
                                      Color.BRIGHT_GREEN)
                else:
                    self._out.writeln("    Remote: None", Color.BRIGHT_GREEN)
            url = getattr(conan, "url", None)
            license_ = getattr(conan, "license", None)
            author = getattr(conan, "author", None)
            if url and show("url"):
                self._out.writeln("    URL: %s" % url, Color.BRIGHT_GREEN)

            if license_ and show("license"):
                if isinstance(license_, (list, tuple, set)):
                    self._out.writeln("    Licenses: %s" % ", ".join(license_), Color.BRIGHT_GREEN)
                else:
                    self._out.writeln("    License: %s" % license_, Color.BRIGHT_GREEN)
            if author and show("author"):
                self._out.writeln("    Author: %s" % author, Color.BRIGHT_GREEN)

            if isinstance(ref, ConanFileReference) and show("recipe"):  # Excludes PROJECT
                self._out.writeln("    Recipe: %s" % node.recipe)
            if isinstance(ref, ConanFileReference) and show("binary"):  # Excludes PROJECT
                self._out.writeln("    Binary: %s" % node.binary)
            if isinstance(ref, ConanFileReference) and show("binary_remote"):  # Excludes PROJECT
                self._out.writeln("    Binary remote: %s" % (node.binary_remote.name if node.binary_remote else "None"))

            if node_times and node_times.get(ref, None) and show("date"):
                self._out.writeln("    Creation date: %s" % node_times.get(ref, None),
                                  Color.BRIGHT_GREEN)

            dependants = [n for node in list_nodes for n in node.inverse_neighbors()]
            if isinstance(ref, ConanFileReference) and show("required"):  # Excludes
                self._out.writeln("    Required by:", Color.BRIGHT_GREEN)
                for d in dependants:
                    ref = d.conan_ref if d.conan_ref else str(d.conanfile)
                    self._out.writeln("        %s" % str(ref), Color.BRIGHT_YELLOW)

            if show("requires"):
                depends = node.neighbors()
                requires = [d for d in depends if not d.build_require]
                build_requires = [d for d in depends if d.build_require]
                if requires:
                    self._out.writeln("    Requires:", Color.BRIGHT_GREEN)
                    for d in requires:
                        self._out.writeln("        %s" % repr(d.conan_ref), Color.BRIGHT_YELLOW)
                if build_requires:
                    self._out.writeln("    Build Requires:", Color.BRIGHT_GREEN)
                    for d in build_requires:
                        self._out.writeln("        %s" % repr(d.conan_ref), Color.BRIGHT_YELLOW)

    def print_search_recipes(self, search_info, pattern, raw, all_remotes_search):
        """ Print all the exported conans information
        param pattern: wildcards, e.g., "opencv/*"
        """
        if not search_info and not raw:
            warn_msg = "There are no packages"
            pattern_msg = " matching the '%s' pattern" % pattern
            self._out.info(warn_msg + pattern_msg if pattern else warn_msg)
            return

        if not raw:
            self._out.info("Existing package recipes:\n")
            for remote_info in search_info:
                if all_remotes_search:
                    self._out.highlight("Remote '%s':" % str(remote_info["remote"]))
                for conan_item in remote_info["items"]:
                    self._print_colored_line(str(conan_item["recipe"]["id"]), indent=0)
        else:
            for remote_info in search_info:
                if all_remotes_search:
                    self._out.writeln("Remote '%s':" % str(remote_info["remote"]))
                for conan_item in remote_info["items"]:
                    self._out.writeln(conan_item["recipe"]["id"])

    def print_search_packages(self, search_info, reference, packages_query,
                              outdated=False):
        assert(isinstance(reference, ConanFileReference))
        self._out.info("Existing packages for recipe %s:\n" % str(reference))
        for remote_info in search_info:
            if remote_info["remote"]:
                self._out.info("Existing recipe in remote '%s':\n" % remote_info["remote"])

            if not remote_info["items"][0]["packages"]:
                if packages_query:
                    warn_msg = "There are no %spackages for reference '%s' matching the query '%s'" % \
                                ("outdated " if outdated else "", str(reference), packages_query)
                elif remote_info["items"][0]["recipe"]:
                    warn_msg = "There are no %spackages for reference '%s', but package recipe found." % \
                            ("outdated " if outdated else "", str(reference))
                self._out.info(warn_msg)
                continue

            reference = remote_info["items"][0]["recipe"]["id"]
            packages = remote_info["items"][0]["packages"]

            # Each package
            for package in packages:
                package_id = package["id"]
                self._print_colored_line("Package_ID", package_id, 1)
                for section in ("options", "settings", "requires"):
                    attr = package[section]
                    if attr:
                        self._print_colored_line("[%s]" % section, indent=2)
                        if isinstance(attr, dict):  # options, settings
                            attr = OrderedDict(sorted(attr.items()))
                            for key, value in attr.items():
                                self._print_colored_line(key, value=value, indent=3)
                        elif isinstance(attr, list):  # full requires
                            for key in sorted(attr):
                                self._print_colored_line(key, indent=3)
                # Always compare outdated with local recipe, simplification,
                # if a remote check is needed install recipe first
                if "outdated" in package:
                    self._print_colored_line("Outdated from recipe: %s" % package["outdated"], indent=2)
                self._out.writeln("")

    def print_profile(self, name, profile):
        self._out.info("Configuration for profile %s:\n" % name)
        self._print_profile_section("settings", profile.settings.items(), separator="=")
        self._print_profile_section("options", profile.options.as_list(), separator="=")
        self._print_profile_section("build_requires", [(key, ", ".join(str(val) for val in values))
                                                       for key, values in
                                                       profile.build_requires.items()])

        envs = []
        for package, env_vars in profile.env_values.data.items():
            for name, value in env_vars.items():
                key = "%s:%s" % (package, name) if package else name
                envs.append((key, value))
        self._print_profile_section("env", envs, separator='=')

    def _print_profile_section(self, name, items, indent=0, separator=": "):
        self._print_colored_line("[%s]" % name, indent=indent, color=Color.BRIGHT_RED)
        for key, value in items:
            self._print_colored_line(key, value=str(value), indent=0, separator=separator)

    def _print_colored_line(self, text, value=None, indent=0, separator=": ", color=None):
        """ Print a colored line depending on its indentation level
            Attributes:
                text: string line
                split_symbol: if you want an output with different in-line colors
                indent_plus: integer to add a plus indentation
        """
        text = text.strip()
        if not text:
            return

        text_color = Printer.INDENT_COLOR.get(indent, Color.BRIGHT_WHITE) if not color else color
        indent_text = ' ' * Printer.INDENT_SPACES * indent
        if value is not None:
            value_color = Color.BRIGHT_WHITE
            self._out.write('%s%s%s' % (indent_text, text, separator), text_color)
            self._out.writeln(value, value_color)
        else:
            self._out.writeln('%s%s' % (indent_text, text), text_color)
