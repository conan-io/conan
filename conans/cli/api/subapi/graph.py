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
                       require_overrides=None, remote=None, update=None):
        """ creates the first, root node of the graph, loading or creating a conanfile
        and initializing it (settings, options) as necessary. Also locking with lockfile
        information, necessary if it has python_requires to be locked, or override-requires
        """
        # TODO: This API is probably not final, but we want it split based on the different things
        #   curently done inside GraphManager. To discuss
        if path and reference:
            raise ConanException("Both path and reference arguments were provided. Please provide "
                                 "only one of them")

        app = ConanApp(self.conan_api.cache_folder)
        # necessary for correct resolution and update of remote python_requires
        remote = [remote] if remote is not None else None
        app.load_remotes(remote, update=update)

        graph_manager, cache = app.graph_manager, app.cache
        reference = reference or path
        # TODO: Improve this interface, not making it public yet, because better to be splitted
        root_node = graph_manager._load_root_node(reference, create_reference, profile_build,
                                                  profile_host, lockfile, root_ref, is_build_require,
                                                  require_overrides)
        return root_node

    @api_method
    def load_graph(self, root_node, profile_host, profile_build, lockfile=None, remote=None,
                   update=False, check_update=False):
        """ Compute the dependency graph, starting from a root package, evaluation the graph with
        the provided configuration in profile_build, and profile_host. The resulting graph is a
        graph of recipes, but packages are not computed yet (package_ids) will be empty in the
        result.
        The result might have errors, like version or configuration conflicts, but it is still
        possible to inspect it. Only trying to install such graph will fail
        :param root_node: the starting point, an already initialized Node structure, as returned
                          by the "load_root_node" api
        :param profile_host: The host profile
        :param profile_build: The build profile
        :param lockfile: A valid lockfile (None by default, means no locked)
        :param remote: TODO: Not clear, cannot be more than 1 now?
        :param update: (False by default), if Conan should look for newer versions or revisions for
                       already existing recipes in the Conan cache
        :param check_update: For "graph info" command, check if there are recipe updates
        """
        app = ConanApp(self.conan_api.cache_folder)

        remote = [remote] if remote is not None else None
        app.load_remotes(remote, update=update, check_updates=check_update)

        assert profile_host is not None
        assert profile_build is not None

        builder = DepsGraphBuilder(app.proxy, app.loader, app.range_resolver)
        deps_graph = builder.load_graph(root_node, profile_host, profile_build, lockfile)

        if lockfile:
            lockfile.update_lock(deps_graph)

        return deps_graph

    @api_method
    def analyze_binaries(self, graph, build_mode=None, remote=None, update=None):
        """ Given a dependency graph, will compute the package_ids of all recipes in the graph, and
        evaluate if they should be built from sources, downloaded from a remote server, of if the
        packages are already in the local Conan cache
        :param graph: a Conan dependency graph, as returned by "load_graph()"
        :param build_mode: TODO: Discuss if this should be a BuildMode object or list of arguments
        :param remote: TODO: Same as above
        :param update: (False by default), if Conan should look for newer versions or revisions for
                       already existing recipes in the Conan cache
        """
        conan_app = ConanApp(self.conan_api.cache_folder)
        remote = [remote] if remote is not None else None
        conan_app.load_remotes(remote, update=update)
        graph.report_graph_error()
        conan_app.binaries_analyzer.evaluate_graph(graph, build_mode)
