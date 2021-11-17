from conans.cli.api.model import Remote
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.cli.output import ConanOutput


class GraphAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def load_graph(self, ref_or_path, profile_host, profile_build, graph_lock, root_ref,
                   build_modes=None, create_reference=None, is_build_require=False,
                   require_overrides=None, remote_name=None, update=False):
        """ Calculate graph and fetch needed recipes
        @param app: The ConanApp instance with all collaborators
        """
        app = ConanApp(self.conan_api.cache_folder)
        # FIXME: remote_name should be remote
        app.load_remotes([Remote(remote_name, None)], update=update)

        assert profile_host is not None
        assert profile_build is not None

        graph_manager, cache = app.graph_manager, app.cache

        out = ConanOutput()
        out.info("Configuration (profile_host):")
        out.info(profile_host.dumps())
        out.info("Configuration (profile_build):")
        out.info(profile_build.dumps())

        deps_graph = graph_manager.load_graph(ref_or_path, create_reference, profile_host,
                                              profile_build,
                                              graph_lock, root_ref, build_modes,
                                              is_build_require=is_build_require,
                                              require_overrides=require_overrides)

        deps_graph.report_graph_error()

        if graph_lock:
            graph_lock.update_lock(deps_graph)

        return deps_graph
