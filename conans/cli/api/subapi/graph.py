from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.cli.output import ConanOutput
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.errors import ConanException


class GraphAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def load_root_node(self, reference, path, profile_host, profile_build, lockfile, root_ref,
                       create_reference=None, is_build_require=False,
                       require_overrides=None):

        if path and reference:
            raise ConanException("Both path and reference arguments were provided. Please provide "
                                 "only one of them")

        app = ConanApp(self.conan_api.cache_folder)
        graph_manager, cache = app.graph_manager, app.cache
        reference = reference or path
        root_node = graph_manager._load_root_node(reference, create_reference, profile_host,
                                                  lockfile, root_ref, is_build_require,
                                                  require_overrides)
        return root_node

    # Maybe we don't want to pass Profile objects to the API?
    @api_method
    def load_graph(self, root_node, profile_host, profile_build, lockfile,
                   remote=None, update=False):
        """ Calculate graph and fetch needed recipes
        """
        app = ConanApp(self.conan_api.cache_folder)

        remote = [remote] if remote is not None else None
        app.load_remotes(remote, update=update)

        assert profile_host is not None
        assert profile_build is not None

        out = ConanOutput()

        builder = DepsGraphBuilder(app.proxy, app.loader, app.range_resolver)
        deps_graph = builder.load_graph(root_node, profile_host, profile_build, lockfile)
        # FIXME: this ugly ouput doesn't belong here
        version_ranges_output = app.range_resolver.output
        if version_ranges_output:
            out.success("Version ranges solved")
            for msg in version_ranges_output:
                out.info("    %s" % msg)
            out.writeln("")
            app.range_resolver.clear_output()

        if lockfile:
            lockfile.update_lock(deps_graph)

        return deps_graph

    @api_method
    def analyze_binaries(self, deps_graph, build_mode=None, remote=None, update=None):
        conan_app = ConanApp(self.conan_api.cache_folder)
        remote = [remote] if remote is not None else None
        conan_app.load_remotes(remote, update=update)
        deps_graph.report_graph_error()
        conan_app.binaries_analyzer.evaluate_graph(deps_graph, build_mode)
