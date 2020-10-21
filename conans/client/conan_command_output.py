import json
import os
from collections import OrderedDict

from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_VIRTUAL
from conans.client.graph.graph import RECIPE_EDITABLE
from conans.client.graph.grapher import Grapher
from conans.client.installer import build_id
from conans.client.printer import Printer
from conans.model.ref import ConanFileReference, PackageReference
from conans.search.binary_html_table import html_binary_graph
from conans.unicode import get_cwd
from conans.util.dates import iso8601_to_str
from conans.util.env_reader import get_env
from conans.util.files import save
from conans import __version__ as client_version
from conans.util.misc import make_tuple


class CommandOutputer(object):

    def __init__(self, output, cache):
        self._output = output
        self._cache = cache

    def print_profile(self, profile, profile_text):
        Printer(self._output).print_profile(profile, profile_text)

    def profile_list(self, profiles):
        for p in sorted(profiles):
            self._output.info(p)

    def remote_list(self, remotes, raw):
        for r in remotes:
            if raw:
                disabled_str = " True" if r.disabled else ""
                self._output.info(
                    "%s %s %s %s" %
                    (r.name, r.url, r.verify_ssl, disabled_str))
            else:
                disabled_str = ", Disabled: True" if r.disabled else ""
                self._output.info(
                    "%s: %s [Verify SSL: %s%s]" %
                    (r.name, r.url, r.verify_ssl, disabled_str))

    def remote_ref_list(self, refs):
        for reference, remote_name in refs.items():
            ref = ConanFileReference.loads(reference)
            self._output.info("%s: %s" % (ref.full_str(), remote_name))

    def remote_pref_list(self, package_references):
        for package_reference, remote_name in package_references.items():
            pref = PackageReference.loads(package_reference)
            self._output.info("%s: %s" % (pref.full_str(), remote_name))

    def build_order(self, info):
        groups = [[ref.copy_clear_rev() for ref in group] for group in info]
        msg = ", ".join(str(s) for s in groups)
        self._output.info(msg)

    def json_build_order(self, info, json_output, cwd):
        data = {"groups": [[repr(ref.copy_clear_rev()) for ref in group] for group in info]}
        json_str = json.dumps(data)
        if json_output is True:  # To the output
            self._output.write(json_str)
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
        self._output.writeln("")
        self._output.info("JSON file created at '%s'" % json_output)

    def _read_dates(self, deps_graph):
        ret = {}
        for node in sorted(deps_graph.nodes):
            ref = node.ref
            if node.recipe not in (RECIPE_CONSUMER, RECIPE_VIRTUAL, RECIPE_EDITABLE):
                manifest = self._cache.package_layout(ref).recipe_manifest()
                ret[ref] = manifest.time_str
        return ret

    def nodes_to_build(self, nodes_to_build):
        self._output.info(", ".join(str(n) for n in nodes_to_build))

    def _handle_json_output(self, data, json_output, cwd):
        json_str = json.dumps(data)

        if json_output is True:
            self._output.write(json_str)
        else:
            if not os.path.isabs(json_output):
                json_output = os.path.join(cwd, json_output)
            save(json_output, json.dumps(data))
            self._output.writeln("")
            self._output.info("JSON file created at '%s'" % json_output)

    def json_nodes_to_build(self, nodes_to_build, json_output, cwd):
        data = [str(n) for n in nodes_to_build]
        self._handle_json_output(data, json_output, cwd)

    def _grab_info_data(self, deps_graph, grab_paths):
        """ Convert 'deps_graph' into consumible information for json and cli """
        compact_nodes = OrderedDict()
        for node in sorted(deps_graph.nodes):
            compact_nodes.setdefault((node.ref, node.package_id), []).append(node)

        build_time_nodes = deps_graph.build_time_nodes()
        remotes = self._cache.registry.load_remotes()
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
                item_data["revision"] = ref.revision

            item_data["reference"] = str(ref)
            item_data["is_ref"] = isinstance(ref, ConanFileReference)
            item_data["display_name"] = conanfile.display_name
            item_data["id"] = package_id
            item_data["build_id"] = build_id(conanfile)

            # Paths
            if isinstance(ref, ConanFileReference) and grab_paths:
                package_layout = self._cache.package_layout(ref, conanfile.short_paths)
                item_data["export_folder"] = package_layout.export()
                item_data["source_folder"] = package_layout.source()
                pref_build_id = build_id(conanfile) or package_id
                pref = PackageReference(ref, pref_build_id)
                item_data["build_folder"] = package_layout.build(pref)

                pref = PackageReference(ref, package_id)
                item_data["package_folder"] = package_layout.package(pref)

            try:
                package_metadata = self._cache.package_layout(ref).load_metadata()
                reg_remote = package_metadata.recipe.remote
                reg_remote = remotes.get(reg_remote)
                if reg_remote:
                    item_data["remote"] = {"name": reg_remote.name, "url": reg_remote.url}
            except Exception:
                pass

            def _add_if_exists(attrib, as_list=False):
                value = getattr(conanfile, attrib, None)
                if value:
                    if not as_list:
                        item_data[attrib] = value
                    else:
                        item_data[attrib] = make_tuple(value)

            _add_if_exists("url")
            _add_if_exists("homepage")
            _add_if_exists("license", as_list=True)
            _add_if_exists("author")
            _add_if_exists("description")
            _add_if_exists("topics", as_list=True)
            _add_if_exists("deprecated")
            _add_if_exists("provides", as_list=True)

            if isinstance(ref, ConanFileReference):
                item_data["recipe"] = node.recipe

                item_data["revision"] = node.ref.revision
                item_data["package_revision"] = node.prev

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
            requires = [d for d in depends if d not in build_time_nodes]
            build_requires = [d for d in depends if d in build_time_nodes]  # TODO: May use build_require_context information

            if requires:
                item_data["requires"] = [repr(d.ref.copy_clear_rev()) for d in requires]

            if build_requires:
                item_data["build_requires"] = [repr(d.ref.copy_clear_rev())
                                               for d in build_requires]

            ret.append(item_data)

        return ret

    def info(self, deps_graph, only, package_filter, show_paths):
        data = self._grab_info_data(deps_graph, grab_paths=show_paths)
        Printer(self._output).print_info(data, only,  package_filter=package_filter,
                                         show_paths=show_paths,
                                         show_revisions=self._cache.config.revisions_enabled)

    def info_graph(self, graph_filename, deps_graph, cwd, template):
        graph = Grapher(deps_graph)
        if not os.path.isabs(graph_filename):
            graph_filename = os.path.join(cwd, graph_filename)

        # FIXME: For backwards compatibility we should prefer here local files (and we are coupling
        #   logic here with the templates).
        assets = {}
        vis_js = os.path.join(self._cache.cache_folder, "vis.min.js")
        if os.path.exists(vis_js):
            assets['vis_js'] = vis_js
        vis_css = os.path.join(self._cache.cache_folder, "vis.min.css")
        if os.path.exists(vis_css):
            assets['vis_css'] = vis_css

        template_folder = os.path.dirname(template.filename)
        save(graph_filename,
             template.render(graph=graph, assets=assets, base_template_path=template_folder,
                             version=client_version))

    def json_info(self, deps_graph, json_output, cwd, show_paths):
        data = self._grab_info_data(deps_graph, grab_paths=show_paths)
        self._handle_json_output(data, json_output, cwd)

    def print_search_references(self, search_info, pattern, raw, all_remotes_search):
        printer = Printer(self._output)
        printer.print_search_recipes(search_info, pattern, raw, all_remotes_search)

    def print_search_packages(self, search_info, reference, packages_query, table, raw,
                              template, outdated=False):
        if table:
            html_binary_graph(search_info, reference, table, template)
        else:
            printer = Printer(self._output)
            printer.print_search_packages(search_info, reference, packages_query, raw,
                                          outdated=outdated)

    def print_revisions(self, reference, revisions, raw, remote_name=None):
        remote_test = " at remote '%s'" % remote_name if remote_name else ""
        if not raw:
            self._output.info("Revisions for '%s'%s:" % (reference, remote_test))
        lines = ["%s (%s)" % (r["revision"],
                              iso8601_to_str(r["time"]) if r["time"] else "No time")
                 for r in revisions]
        self._output.writeln("\n".join(lines))

    def print_dir_list(self, list_files, path, raw):
        if not raw:
            self._output.info("Listing directory '%s':" % path)
            self._output.writeln("\n".join([" %s" % i for i in list_files]))
        else:
            self._output.writeln("\n".join(list_files))

    def print_file_contents(self, contents, file_name, raw):
        if raw or not self._output.is_terminal:
            self._output.writeln(contents)
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

        self._output.write(highlight(contents, lexer, TerminalFormatter()))

    def print_user_list(self, info):
        for remote in info["remotes"]:
            authenticated = " [Authenticated]" if remote["authenticated"] else ""
            anonymous = " (anonymous)" if not remote["user_name"] else ""
            self._output.info("Current user of remote '%s' set to: '%s'%s%s" %
                              (remote["name"], str(remote["user_name"]), anonymous, authenticated))

    def print_user_set(self, remote_name, prev_user, user):
        previous_username = prev_user or "None"
        previous_anonymous = " (anonymous)" if not prev_user else ""
        username = user or "None"
        anonymous = " (anonymous)" if not user else ""

        if prev_user == user:
            self._output.info("User of remote '%s' is already '%s'%s" %
                              (remote_name, previous_username, previous_anonymous))
        else:
            self._output.info("Changed user of remote '%s' from '%s'%s to '%s'%s" %
                              (remote_name, previous_username, previous_anonymous, username,
                               anonymous))
