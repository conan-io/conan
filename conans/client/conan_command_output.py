import copy
import json
import os
from collections import OrderedDict

from conans import __version__ as client_version
from conans.cli.output import ConanOutput
from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_VIRTUAL
from conans.client.graph.graph import RECIPE_EDITABLE
from conans.client.graph.grapher import Grapher
from conans.client.installer import build_id
from conans.client.printer import Printer

from conans.model.recipe_ref import RecipeReference
from conans.util.files import save
from conans.util.misc import make_tuple


class CommandOutputer(object):

    def __init__(self):
        self._output = ConanOutput()

    def json_output(self, info, json_output, cwd):
        cwd = os.path.abspath(cwd or os.getcwd())
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
                # FIXME: Not access to the cache should be available here
                # manifest = self._cache.ref_layout(ref).recipe_manifest()
                # ret[ref] = manifest.time_str
                ret[ref] = ""
        return ret

    def _handle_json_output(self, data, json_output, cwd):
        json_str = json.dumps(data)

        if json_output is True:
            self._output.info(json_str)
        else:
            if not os.path.isabs(json_output):
                json_output = os.path.join(cwd, json_output)
            save(json_output, json.dumps(data))
            self._output.info("")
            self._output.info("JSON file created at '%s'" % json_output)

    def _grab_info_data(self, deps_graph, grab_paths):
        """ Convert 'deps_graph' into consumible information for json and cli """
        compact_nodes = OrderedDict()
        for node in sorted(deps_graph.nodes):
            compact_nodes.setdefault((node.ref, node.package_id), []).append(node)

        build_time_nodes = deps_graph.build_time_nodes()
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
            item_data["is_ref"] = isinstance(ref, RecipeReference)
            item_data["display_name"] = conanfile.display_name
            item_data["id"] = package_id
            item_data["build_id"] = build_id(conanfile)
            item_data["context"] = conanfile.context

            python_requires = getattr(conanfile, "python_requires", None)
            if python_requires and not isinstance(python_requires, dict):  # no old python requires
                item_data["python_requires"] = [r.repr_notime()
                                                for r in conanfile.python_requires.all_refs()]

            # Paths
            if isinstance(ref, RecipeReference) and grab_paths:
                # ref already has the revision ID, not needed to get it again
                # FIXME: Not access to the cache should be available here, this information
                #        should be provided by the conan_api

                # ref_layout = self._cache.ref_layout(ref)
                # item_data["export_folder"] = ref_layout.export()
                # item_data["source_folder"] = ref_layout.source()
                # pref_build_id = build_id(conanfile) or package_id
                # pref_build = self._cache.get_latest_package_reference(PackageReference(ref, pref_build_id))
                # pref_package = self._cache.get_latest_package_reference(PackageReference(ref, package_id))
                # item_data["build_folder"] = self._cache.get_pkg_layout(pref_build).build()
                # item_data["package_folder"] = self._cache.get_pkg_layout(pref_package).package()

                item_data["export_folder"] = "unknown"
                item_data["source_folder"] = "unknown"
                item_data["build_folder"] = "unknown"
                item_data["package_folder"] = "unknown"

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
            _add_if_exists("scm")

            if isinstance(ref, RecipeReference):
                item_data["recipe"] = node.recipe

                item_data["revision"] = node.ref.revision
                item_data["package_revision"] = node.prev

                item_data["binary"] = node.binary
                if node.binary_remote:
                    item_data["binary_remote"] = node.binary_remote.name

            node_times = self._read_dates(deps_graph)
            if node_times and node_times.get(ref, None):
                item_data["creation_date"] = node_times.get(ref, None)

            if isinstance(ref, RecipeReference):
                dependants = [n for node in list_nodes for n in node.inverse_neighbors()]
                required = [d.conanfile for d in dependants if d.recipe != RECIPE_VIRTUAL]
                if required:
                    item_data["required_by"] = [d.display_name for d in required]

            depends = node.neighbors()
            requires = [d for d in depends if d not in build_time_nodes]
            build_requires = [d for d in depends if d in build_time_nodes]  # TODO: May use build_require_context information

            if requires:
                item_data["requires"] = []
                for d in requires:
                    _tmp = copy.copy(d.ref)
                    _tmp.revision = None
                    item_data["requires"].append(repr(_tmp))

            if build_requires:
                item_data["build_requires"] = []
                for d in build_requires:
                    _tmp = copy.copy(d.ref)
                    _tmp.revision = None
                    item_data["build_requires"].append(repr(_tmp))

            ret.append(item_data)

        return ret

    def info(self, deps_graph, only, package_filter, show_paths):
        data = self._grab_info_data(deps_graph, grab_paths=show_paths)
        Printer(self._output).print_info(data, only,  package_filter=package_filter,
                                         show_paths=show_paths)

    def info_graph(self, graph_filename, deps_graph, cwd, template, cache_folder):
        graph = Grapher(deps_graph)
        if not os.path.isabs(graph_filename):
            graph_filename = os.path.join(cwd, graph_filename)

        # FIXME: For backwards compatibility we should prefer here local files (and we are coupling
        #   logic here with the templates).
        assets = {}
        vis_js = os.path.join(cache_folder, "vis.min.js")
        if os.path.exists(vis_js):
            assets['vis_js'] = vis_js
        vis_css = os.path.join(cache_folder, "vis.min.css")
        if os.path.exists(vis_css):
            assets['vis_css'] = vis_css

        template_folder = os.path.dirname(template.filename)
        save(graph_filename,
             template.render(graph=graph, assets=assets, base_template_path=template_folder,
                             version=client_version))

    def json_info(self, deps_graph, json_output, cwd, show_paths):
        data = self._grab_info_data(deps_graph, grab_paths=show_paths)
        self._handle_json_output(data, json_output, cwd)

    def print_dir_list(self, list_files, path, raw):
        if not raw:
            self._output.info("Listing directory '%s':" % path)
            self._output.info("\n".join([" %s" % i for i in list_files]))
        else:
            self._output.info("\n".join(list_files))

    def print_file_contents(self, contents, file_name, raw):
        if raw or not self._output.is_terminal:
            self._output.info(contents)
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

        self._output.info(highlight(contents, lexer, TerminalFormatter()))
