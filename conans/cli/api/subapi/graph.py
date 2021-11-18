import os

from conans.cli.api.model import Remote
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.cli.output import ConanOutput
from conans.errors import ConanException
from conans.model.graph_lock import Lockfile, LOCKFILE
from conans.model.recipe_ref import RecipeReference


class GraphAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def load_graph(self, reference, path, profile_host, profile_build, graph_lock, root_ref,
                   install_folder, base_folder, build_modes=None, create_reference=None,
                   is_build_require=False, require_overrides=None, remote_name=None, update=False,
                   test=None):
        """ Calculate graph and fetch needed recipes
        @param ref_or_path: ...
        """
        app = ConanApp(self.conan_api.cache_folder)
        # FIXME: remote_name should be remote
        app.load_remotes([Remote(remote_name, None)], update=update)

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
                                              graph_lock, root_ref, build_modes,
                                              is_build_require=is_build_require,
                                              require_overrides=require_overrides)

        root_node = deps_graph.root
        conanfile = root_node.conanfile

        if hasattr(conanfile, "layout") and not test:
            conanfile_path = os.path.dirname(ref_or_path) if not isinstance(ref_or_path,
                                                                            RecipeReference) else None
            conanfile.folders.set_base_install(conanfile_path)
            conanfile.folders.set_base_imports(conanfile_path)
            conanfile.folders.set_base_generators(conanfile_path)
        else:
            conanfile.folders.set_base_install(install_folder)
            conanfile.folders.set_base_imports(install_folder)
            conanfile.folders.set_base_generators(base_folder)

        deps_graph.report_graph_error()

        if graph_lock:
            graph_lock.update_lock(deps_graph)

        return deps_graph

    # should this be an API method?
    @api_method
    def get_graph_lock(self, lockfile):
        graph_lock = None
        if lockfile:
            lockfile = lockfile if os.path.isfile(lockfile) else os.path.join(lockfile, LOCKFILE)
            graph_lock = Lockfile.load(lockfile)
            ConanOutput().info("Using lockfile: '{}'".format(lockfile))
        return graph_lock
