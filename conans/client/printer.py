from collections import OrderedDict

from conans.paths import SimplePaths

from conans.client.output import Color
from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference
from conans.client.installer import build_id
import fnmatch


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

    def print_graph(self, deps_graph, registry):
        """ Simple pretty printing of a deps graph, can be improved
        with options, info like licenses, etc
        """
        self._out.writeln("Requirements", Color.BRIGHT_YELLOW)
        for node in sorted(deps_graph.nodes):
            ref, _ = node
            if not ref:
                continue
            remote = registry.get_ref(ref)
            from_text = "from local" if not remote else "from %s" % remote.name
            self._out.writeln("    %s %s" % (repr(ref), from_text), Color.BRIGHT_CYAN)
        self._out.writeln("Packages", Color.BRIGHT_YELLOW)
        for node in sorted(deps_graph.nodes):
            ref, conanfile = node
            if not ref:
                continue
            ref = PackageReference(ref, conanfile.info.package_id())
            self._out.writeln("    %s" % repr(ref), Color.BRIGHT_CYAN)
        self._out.writeln("")

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

    def print_info(self, deps_graph, project_reference, _info, registry, graph_updates_info=None,
                   remote=None, node_times=None, path_resolver=None, package_filter=None,
                   show_paths=False):
        """ Print the dependency information for a conan file

            Attributes:
                deps_graph: the dependency graph of conan file references to print
                placeholder_reference: the conan file reference that represents the conan
                                       file for a project on the path. This may be None,
                                       in which case the project itself will not be part
                                       of the printed dependencies.
                remote: Remote specified in install command.
                        Could be different from the registry one.
        """
        if _info is None:  # No filter
            def show(_):
                return True
        else:
            _info_lower = [s.lower() for s in _info]

            def show(field):
                return field in _info_lower

        graph_updates_info = graph_updates_info or {}
        for node in sorted(deps_graph.nodes):
            ref, conan = node
            if not ref:
                # ref is only None iff info is being printed for a project directory, and
                # not a passed in reference
                if project_reference is None:
                    continue
                else:
                    ref = project_reference
            if package_filter and not fnmatch.fnmatch(str(ref), package_filter):
                continue

            self._out.writeln("%s" % str(ref), Color.BRIGHT_CYAN)
            reg_remote = registry.get_ref(ref)
            # Excludes PROJECT fake reference
            remote_name = remote
            if reg_remote and not remote:
                remote_name = reg_remote.name

            if show("id"):
                id_ = conan.info.package_id()
                self._out.writeln("    ID: %s" % id_, Color.BRIGHT_GREEN)
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

            if isinstance(ref, ConanFileReference) and show("update"):  # Excludes PROJECT
                update = graph_updates_info.get(ref)
                update_messages = {
                 None: ("Version not checked", Color.WHITE),
                 0: ("You have the latest version (%s)" % remote_name, Color.BRIGHT_GREEN),
                 1: ("There is a newer version (%s)" % remote_name, Color.BRIGHT_YELLOW),
                 -1: ("The local file is newer than remote's one (%s)" % remote_name,
                      Color.BRIGHT_RED)
                }
                self._out.writeln("    Updates: %s" % update_messages[update][0],
                                  update_messages[update][1])

            if node_times and node_times.get(ref, None) and show("date"):
                self._out.writeln("    Creation date: %s" % node_times.get(ref, None),
                                  Color.BRIGHT_GREEN)

            dependants = deps_graph.inverse_neighbors(node)
            if isinstance(ref, ConanFileReference) and show("required"):  # Excludes
                self._out.writeln("    Required by:", Color.BRIGHT_GREEN)
                for d in dependants:
                    ref = d.conan_ref if d.conan_ref else project_reference
                    self._out.writeln("        %s" % str(ref), Color.BRIGHT_YELLOW)

            if show("requires"):
                depends = deps_graph.neighbors(node)
                if depends:
                    self._out.writeln("    Requires:", Color.BRIGHT_GREEN)
                    for d in depends:
                        self._out.writeln("        %s" % repr(d.conan_ref), Color.BRIGHT_YELLOW)

    def print_search_recipes(self, references, pattern, raw):
        """ Print all the exported conans information
        param pattern: wildcards, e.g., "opencv/*"
        """
        if not references and not raw:
            warn_msg = "There are no packages"
            pattern_msg = " matching the %s pattern" % pattern
            self._out.info(warn_msg + pattern_msg if pattern else warn_msg)
            return

        if not raw:
            self._out.info("Existing package recipes:\n")
            for conan_ref in sorted(references):
                self._print_colored_line(str(conan_ref), indent=0)
        else:
            self._out.writeln("\n".join([str(ref) for ref in references]))

    def print_search_packages(self, packages_props, reference, recipe_hash, packages_query):
        if not packages_props:
            if packages_query:
                warn_msg = "There are no packages for reference '%s' matching the query '%s'" % (str(reference),
                                                                                                 packages_query)
            else:
                warn_msg = "There are no packages for pattern '%s'" % str(reference)
            self._out.info(warn_msg)
            return

        self._out.info("Existing packages for recipe %s:\n" % str(reference))
        # Each package
        for package_id, properties in sorted(packages_props.items()):
            self._print_colored_line("Package_ID", package_id, 1)
            for section in ("options", "settings", "full_requires"):
                attrs = properties.get(section, [])
                if attrs:
                    section_name = {"full_requires": "requires"}.get(section, section)
                    self._print_colored_line("[%s]" % section_name, indent=2)
                    if isinstance(attrs, dict):  # options, settings
                        attrs = OrderedDict(sorted(attrs.items()))
                        for key, value in attrs.items():
                            self._print_colored_line(key, value=value, indent=3)
                    elif isinstance(attrs, list):  # full requires
                        for key in sorted(attrs):
                            self._print_colored_line(key, indent=3)
            package_recipe_hash = properties.get("recipe_hash", None)
            # Always compare outdated with local recipe, simplification,
            # if a remote check is needed install recipe first
            if recipe_hash:
                self._print_colored_line("outdated from recipe: %s" % (recipe_hash != package_recipe_hash), indent=2)
            self._out.writeln("")

    def print_profile(self, name, profile):
        self._out.info("Configuration for profile %s:\n" % name)
        self._print_profile_section("settings", profile.settings.items())

        envs = []
        for package, env_vars in profile.env_values.data.items():
            for name, value in env_vars.items():
                key = "%s:%s" % (package, name) if package else name
                envs.append((key, value))
        self._print_profile_section("env", envs, separator='=')
        scopes = profile.scopes.dumps().splitlines()
        self._print_colored_line("[scopes]")
        for scope in scopes:
            self._print_colored_line(scope, indent=1)

    def _print_profile_section(self, name, items, indent=0, separator=": "):
        self._print_colored_line("[%s]" % name, indent=indent)
        for key, value in items:
            self._print_colored_line(key, value=str(value), indent=indent+1, separator=separator)

    def _print_colored_line(self, text, value=None, indent=0, separator=": "):
        """ Print a colored line depending on its indentation level
            Attributes:
                text: string line
                split_symbol: if you want an output with different in-line colors
                indent_plus: integer to add a plus indentation
        """
        text = text.strip()
        if not text:
            return

        text_color = Printer.INDENT_COLOR.get(indent, Color.BRIGHT_WHITE)
        indent_text = ' ' * Printer.INDENT_SPACES * indent
        if value is not None:
            value_color = Color.BRIGHT_WHITE
            self._out.write('%s%s%s' % (indent_text, text, separator), text_color)
            self._out.writeln(value, value_color)
        else:
            self._out.writeln('%s%s' % (indent_text, text), text_color)
