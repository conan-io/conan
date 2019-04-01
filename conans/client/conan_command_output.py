import json
import os
from collections import OrderedDict

from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_VIRTUAL
from conans.client.graph.graph import RECIPE_EDITABLE
from conans.client.installer import build_id
from conans.client.printer import Printer
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths.simple_paths import SimplePaths
from conans.search.binary_html_table import html_binary_graph
from conans.unicode import get_cwd
from conans.util.dates import iso8601_to_str
from conans.util.env_reader import get_env
from conans.util.files import save


class CommandOutputer(object):

    def __init__(self, user_io, cache):
        self.user_io = user_io
        self.cache = cache

    def writeln(self, value):
        self.user_io.out.writeln(value)

    def print_profile(self, profile, profile_text):
        Printer(self.user_io.out).print_profile(profile, profile_text)

    def profile_list(self, profiles):
        for p in sorted(profiles):
            self.user_io.out.info(p)

    def remote_list(self, remotes, raw):
        for r in remotes:
            if raw:
                self.user_io.out.info("%s %s %s" % (r.name, r.url, r.verify_ssl))
            else:
                self.user_io.out.info("%s: %s [Verify SSL: %s]" % (r.name, r.url, r.verify_ssl))

    def remote_ref_list(self, refs):
        for reference, remote_name in refs.items():
            ref = ConanFileReference.loads(reference)
            self.user_io.out.info("%s: %s" % (ref.full_repr(), remote_name))

    def remote_pref_list(self, package_references):
        for package_reference, remote_name in package_references.items():
            pref = PackageReference.loads(package_reference)
            self.user_io.out.info("%s: %s" % (pref.full_repr(), remote_name))

    def build_order(self, info):
        msg = ", ".join(str(s) for s in info)
        self.user_io.out.info(msg)

    def json_build_order(self, info, json_output, cwd):
        data = {"groups": [[str(ref) for ref in group] for group in info]}
        json_str = json.dumps(data)
        if json_output is True:  # To the output
            self.user_io.out.write(json_str)
        else:  # Path to a file
            cwd = os.path.abspath(cwd or get_cwd())
            if not os.path.isabs(json_output):
                json_output = os.path.join(cwd, json_output)
            save(json_output, json_str)

    def json_output(self, info, json_output, cwd):
        cwd = os.path.abspath(cwd or get_cwd())
        if not os.path.isabs(json_output):
            json_output = os.path.join(cwd, json_output)

        def date_handler(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            else:
                raise TypeError("Unserializable object {} of type {}".format(obj, type(obj)))

        save(json_output, json.dumps(info, default=date_handler))
        self.user_io.out.writeln("")
        self.user_io.out.info("JSON file created at '%s'" % json_output)

    def _read_dates(self, deps_graph):
        ret = {}
        for node in sorted(deps_graph.nodes):
            ref = node.ref
            if node.recipe not in (RECIPE_CONSUMER, RECIPE_VIRTUAL, RECIPE_EDITABLE):
                manifest = self.cache.package_layout(ref).recipe_manifest()
                ret[ref] = manifest.time_str
        return ret

    def nodes_to_build(self, nodes_to_build):
        self.user_io.out.info(", ".join(str(n) for n in nodes_to_build))

    def _handle_json_output(self, data, json_output, cwd):
        json_str = json.dumps(data)

        if json_output is True:
            self.user_io.out.write(json_str)
        else:
            if not os.path.isabs(json_output):
                json_output = os.path.join(cwd, json_output)
            save(json_output, json.dumps(data))
            self.user_io.out.writeln("")
            self.user_io.out.info("JSON file created at '%s'" % json_output)

    def json_nodes_to_build(self, nodes_to_build, json_output, cwd):
        data = [str(n) for n in nodes_to_build]
        self._handle_json_output(data, json_output, cwd)

    def _grab_info_data(self, deps_graph, grab_paths):
        """ Convert 'deps_graph' into consumible information for json and cli """
        compact_nodes = OrderedDict()
        for node in sorted(deps_graph.nodes):
            compact_nodes.setdefault((node.ref, node.package_id), []).append(node)

        ret = []
        for (ref, package_id), list_nodes in compact_nodes.items():
            node = list_nodes[0]
            if node.recipe == RECIPE_VIRTUAL:
                continue

            item_data = {}
            conanfile = node.conanfile
            if node.recipe == RECIPE_CONSUMER:
                ref = str(conanfile)
            else:
                item_data["revision"] = str(ref.revision)

            item_data["reference"] = str(ref)
            item_data["is_ref"] = isinstance(ref, ConanFileReference)
            item_data["display_name"] = conanfile.display_name
            item_data["id"] = package_id
            item_data["build_id"] = build_id(conanfile)

            # Paths
            if isinstance(ref, ConanFileReference) and grab_paths:
                item_data["export_folder"] = self.cache.export(ref)
                item_data["source_folder"] = self.cache.source(ref, conanfile.short_paths)
                if isinstance(self.cache, SimplePaths):
                    # @todo: check if this is correct or if it must always be package_id
                    package_id = build_id(conanfile) or package_id
                    pref = PackageReference(ref, package_id)
                    item_data["build_folder"] = self.cache.build(pref, conanfile.short_paths)

                    pref = PackageReference(ref, package_id)
                    item_data["package_folder"] = self.cache.package(pref, conanfile.short_paths)

            try:
                reg_remote = self.cache.registry.refs.get(ref)
                if reg_remote:
                    item_data["remote"] = {"name": reg_remote.name, "url": reg_remote.url}
            except:
                pass

            def _add_if_exists(attrib, as_list=False):
                value = getattr(conanfile, attrib, None)
                if value:
                    if not as_list:
                        item_data[attrib] = value
                    else:
                        item_data[attrib] = list(value) if isinstance(value, (list, tuple, set)) \
                            else [value, ]

            _add_if_exists("url")
            _add_if_exists("homepage")
            _add_if_exists("license", as_list=True)
            _add_if_exists("author")
            _add_if_exists("topics", as_list=True)

            if isinstance(ref, ConanFileReference):
                item_data["recipe"] = node.recipe

                if get_env("CONAN_CLIENT_REVISIONS_ENABLED", False) and node.ref.revision:
                    item_data["revision"] = node.ref.revision

                item_data["binary"] = node.binary
                if node.binary_remote:
                    item_data["binary_remote"] = node.binary_remote.name

            node_times = self._read_dates(deps_graph)
            if node_times and node_times.get(ref, None):
                item_data["creation_date"] = node_times.get(ref, None)

            if isinstance(ref, ConanFileReference):
                dependants = [n for node in list_nodes for n in node.inverse_neighbors()]
                required = [d.conanfile for d in dependants if d.recipe != RECIPE_VIRTUAL]
                if required:
                    item_data["required_by"] = [d.display_name for d in required]

            depends = node.neighbors()
            requires = [d for d in depends if not d.build_require]
            build_requires = [d for d in depends if d.build_require]

            if requires:
                item_data["requires"] = [repr(d.ref) for d in requires]

            if build_requires:
                item_data["build_requires"] = [repr(d.ref) for d in build_requires]

            ret.append(item_data)

        return ret

    def info(self, deps_graph, only, package_filter, show_paths):
        data = self._grab_info_data(deps_graph, grab_paths=show_paths)
        Printer(self.user_io.out).print_info(data, only,  package_filter=package_filter,
                                             show_paths=show_paths,
                                             show_revisions=self.cache.config.revisions_enabled)

    def info_graph(self, graph_filename, deps_graph, cwd):
        if graph_filename.endswith(".html"):
            from conans.client.graph.grapher import ConanHTMLGrapher
            grapher = ConanHTMLGrapher(deps_graph, self.cache.conan_folder)
        else:
            from conans.client.graph.grapher import ConanGrapher
            grapher = ConanGrapher(deps_graph)

        cwd = os.path.abspath(cwd or get_cwd())
        if not os.path.isabs(graph_filename):
            graph_filename = os.path.join(cwd, graph_filename)
        grapher.graph_file(graph_filename)

    def json_info(self, deps_graph, json_output, cwd, show_paths):
        data = self._grab_info_data(deps_graph, grab_paths=show_paths)
        self._handle_json_output(data, json_output, cwd)

    def print_search_references(self, search_info, pattern, raw, all_remotes_search):
        printer = Printer(self.user_io.out)
        printer.print_search_recipes(search_info, pattern, raw, all_remotes_search)

    def print_search_packages(self, search_info, reference, packages_query, table,
                              outdated=False):
        if table:
            html_binary_graph(search_info, reference, table)
        else:
            printer = Printer(self.user_io.out)
            printer.print_search_packages(search_info, reference, packages_query,
                                          outdated=outdated)

    def print_revisions(self, reference, revisions, remote_name=None):
        remote_test = " at remote '%s'" % remote_name if remote_name else ""
        self.user_io.out.info("Revisions for '%s'%s:" % (reference, remote_test))
        lines = ["%s (%s)" % (r["revision"],
                              iso8601_to_str(r["time"]) if r["time"] else "No time")
                 for r in revisions]
        self.user_io.out.writeln("\n".join(lines))

    def print_dir_list(self, list_files, path, raw):
        if not raw:
            self.user_io.out.info("Listing directory '%s':" % path)
            self.user_io.out.writeln("\n".join([" %s" % i for i in list_files]))
        else:
            self.user_io.out.writeln("\n".join(list_files))

    def print_file_contents(self, contents, file_name, raw):
        if raw or not self.user_io.out.is_terminal:
            self.user_io.out.writeln(contents)
            return

        from pygments import highlight
        from pygments.lexers import PythonLexer, IniLexer, TextLexer
        from pygments.formatters import TerminalFormatter

        if file_name.endswith(".py"):
            lexer = PythonLexer()
        elif file_name.endswith(".txt"):
            lexer = IniLexer()
        else:
            lexer = TextLexer()

        self.user_io.out.write(highlight(contents, lexer, TerminalFormatter()))

    def print_user_list(self, info):
        for remote in info["remotes"]:
            authenticated = " [Authenticated]" if remote["authenticated"] else ""
            anonymous = " (anonymous)" if not remote["user_name"] else ""
            self.user_io.out.info("Current user of remote '%s' set to: '%s'%s%s" %
                                  (remote["name"], str(remote["user_name"]), anonymous,
                                   authenticated))

    def print_user_set(self, remote_name, prev_user, user):
        previous_username = prev_user or "None"
        previous_anonymous = " (anonymous)" if not prev_user else ""
        username = user or "None"
        anonymous = " (anonymous)" if not user else ""

        if prev_user == user:
            self.user_io.out.info("User of remote '%s' is already '%s'%s" %
                                  (remote_name, previous_username, previous_anonymous))
        else:
            self.user_io.out.info("Changed user of remote '%s' from '%s'%s to '%s'%s" %
                                  (remote_name, previous_username, previous_anonymous, username,
                                   anonymous))
