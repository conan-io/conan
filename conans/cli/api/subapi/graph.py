from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.cli.output import ConanOutput
from conans.errors import ConanException


class GraphAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    # Maybe we don't want to pass Profile objects to the API?
    @api_method
    def load_graph(self, reference, path, profile_host, profile_build, lockfile, root_ref,
                   build_modes=None, create_reference=None, is_build_require=False,
                   require_overrides=None, remote=None, update=False):
        """ Calculate graph and fetch needed recipes
        @param reference: Conan reference to build the graph for
        @param path: Path to the conanfile.py or conanfile.txt to build the graph
        @param profile_host: Profile for the host context
        @param profile_build: Profile for the build context
        @param lockfile: Locked graph to use to build the graph
        @param root_ref: RecipeReference with fields (name, version, user, channel) that may be missing in the conanfile provided as argument
        @param build_modes:
        @param create_reference:
        @param is_build_require:
        @param require_overrides:
        @param remote:
        @param update:
        """
        if path and reference:
            raise ConanException("Both path and reference arguments were provided. Please provide "
                                 "only one of them")

        app = ConanApp(self.conan_api.cache_folder)

        app.load_remotes([remote], update=update)

        assert profile_host is not None
        assert profile_build is not None

        if path and reference:
            raise ConanException("Both path and reference arguments were provided. Please provide "
                                 "only one of them")

        graph_manager, cache = app.graph_manager, app.cache

        out = ConanOutput()
        out.info("Configuration (profile_host):")
        out.info(profile_host.dumps())
        out.info("Configuration (profile_build):")
        out.info(profile_build.dumps())

        ref_or_path = reference or path
        deps_graph = graph_manager.load_graph(ref_or_path, create_reference, profile_host,
                                              profile_build,
                                              lockfile, root_ref, build_modes,
                                              is_build_require=is_build_require,
                                              require_overrides=require_overrides)

        deps_graph.report_graph_error()

        if lockfile:
            lockfile.update_lock(deps_graph)

        return deps_graph
