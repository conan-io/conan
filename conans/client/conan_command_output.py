import os
import json

from conans.model.ref import ConanFileReference

from conans.client.printer import Printer

from conans.client.remote_registry import RemoteRegistry

from conans.client.grapher import ConanHTMLGrapher, ConanGrapher

from conans.client.conan_api import prepare_cwd
from conans.util.files import save


class CommandOutputer(object):

    def __init__(self, user_io, client_cache):
        self.user_io = user_io
        self.client_cache = client_cache

    def build_order(self, info):
        msg = ", ".join(str(s) for s in info)
        self.user_io.out.info(msg)

    def json_build_order(self, info, json_output, cwd):
        data = {"groups": [[str(ref) for ref in group] for group in info]}
        json_str = json.dumps(data)
        if json_output is True: # To the output
            self.user_io.out.write(json_str)
        else: # Path to a file
            cwd = prepare_cwd(cwd)
            if not os.path.isabs(json_output):
                json_output = os.path.join(cwd, json_output)
            save(json_output, json_str)

    def _read_dates(self, deps_graph):
        ret = {}
        for ref, _ in sorted(deps_graph.nodes):
            if ref:
                manifest = self.client_cache.load_manifest(ref)
                ret[ref] = manifest.time_str
        return ret

    def nodes_to_build(self, nodes_to_build):
        self.user_io.out.info(", ".join(nodes_to_build))

    def info(self, deps_graph, graph_updates_info, only, remote, package_filter, show_paths, project_reference):
        registry = RemoteRegistry(self.client_cache.registry, self.user_io.out)
        Printer(self.user_io.out).print_info(deps_graph, project_reference,
                                             only, registry, graph_updates_info=graph_updates_info,
                                             remote=remote, node_times=self._read_dates(deps_graph),
                                             path_resolver=self.client_cache, package_filter=package_filter,
                                             show_paths=show_paths)

    def info_graph(self, graph_filename, deps_graph, project_reference, cwd):
        if graph_filename.endswith(".html"):
            grapher = ConanHTMLGrapher(project_reference, deps_graph)
        else:
            grapher = ConanGrapher(project_reference, deps_graph)

        cwd = prepare_cwd(cwd)
        if not os.path.isabs(graph_filename):
            graph_filename = os.path.join(cwd, graph_filename)
        grapher.graph_file(graph_filename)

    def print_search_references(self, references, pattern, raw):
        printer = Printer(self.user_io.out)
        printer.print_search_recipes(references, pattern, raw)

    def print_search_packages(self, ordered_packages, pattern, recipe_hash, packages_query):
        printer = Printer(self.user_io.out)
        printer.print_search_packages(ordered_packages, pattern, recipe_hash, packages_query)
