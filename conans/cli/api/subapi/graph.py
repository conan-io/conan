from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.client.graph.graph import Node, RECIPE_CONSUMER, CONTEXT_HOST, RECIPE_VIRTUAL
from conans.client.graph.graph_binaries import GraphBinariesAnalyzer
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.client.graph.profile_node_definer import initialize_conanfile_profile, consumer_definer

from conans.errors import ConanException

from conans.model.recipe_ref import RecipeReference


class GraphAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def load_root_consumer_conanfile(self, path, profile_host, profile_build,
                                     name=None, version=None, user=None, channel=None,
                                     update=None, remotes=None, lockfile=None):
        app = ConanApp(self.conan_api.cache_folder)
        # necessary for correct resolution and update of remote python_requires
        app.load_remotes(remotes, update=update)

        if path.endswith(".py"):
            conanfile = app.loader.load_consumer(path,
                                                 name=name,
                                                 version=version,
                                                 user=user,
                                                 channel=channel,
                                                 graph_lock=lockfile)
            ref = RecipeReference(conanfile.name, conanfile.version,
                                  conanfile.user, conanfile.channel)
            initialize_conanfile_profile(conanfile, profile_build, profile_host, CONTEXT_HOST,
                                         False, ref)
            if ref.name:
                profile_host.options.scope(ref)
            root_node = Node(ref, conanfile, context=CONTEXT_HOST, recipe=RECIPE_CONSUMER, path=path)
        else:
            conanfile = app.loader.load_conanfile_txt(path)
            consumer_definer(conanfile, profile_host)
            root_node = Node(None, conanfile, context=CONTEXT_HOST, recipe=RECIPE_CONSUMER,
                             path=path)
        return root_node

    @api_method
    def load_root_test_conanfile(self, path, tested_reference, profile_host, profile_build,
                                 update=None, remotes=None, lockfile=None):
        """
        create and initialize a root node from a test_package/conanfile.py consumer
        @param lockfile: Might be good to lock python-requires, build-requires
        @param path: The full path to the test_package/conanfile.py being used
        @param tested_reference: The full RecipeReference of the tested package
        @param profile_host:
        @param profile_build:
        @param update:
        @param remotes:
        @return: a graph Node, recipe=RECIPE_CONSUMER
        """

        app = ConanApp(self.conan_api.cache_folder)
        # necessary for correct resolution and update of remote python_requires
        app.load_remotes(remotes, update=update)

        loader = app.loader
        profile_host.options.scope(tested_reference)

        # do not try apply lock_python_requires for test_package/conanfile.py consumer
        conanfile = loader.load_consumer(path, user=tested_reference.user,
                                         channel=tested_reference.channel,
                                         graph_lock=lockfile)
        initialize_conanfile_profile(conanfile, profile_build, profile_host, CONTEXT_HOST, False)
        conanfile.display_name = "%s (test package)" % str(tested_reference)
        conanfile.output.scope = conanfile.display_name
        conanfile.tested_reference_str = repr(tested_reference)

        ref = RecipeReference(conanfile.name, conanfile.version, tested_reference.user,
                              tested_reference.channel)
        root_node = Node(ref, conanfile, recipe=RECIPE_CONSUMER, context=CONTEXT_HOST, path=path)
        return root_node

    @api_method
    def load_root_virtual_conanfile(self, profile_host, requires=None, tool_requires=None):
        if not requires and not tool_requires:
            raise ConanException("Provide requires or tool_requires")
        app = ConanApp(self.conan_api.cache_folder)
        conanfile = app.loader.load_virtual(requires=requires,  tool_requires=tool_requires)
        consumer_definer(conanfile, profile_host)
        root_node = Node(ref=None, conanfile=conanfile, context=CONTEXT_HOST, recipe=RECIPE_VIRTUAL)
        return root_node

    @api_method
    def load_graph(self, root_node, profile_host, profile_build, lockfile=None, remotes=None,
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
        :param remotes: list of remotes we want to check
        :param update: (False by default), if Conan should look for newer versions or revisions for
                       already existing recipes in the Conan cache
        :param check_update: For "graph info" command, check if there are recipe updates
        """
        app = ConanApp(self.conan_api.cache_folder)

        app.load_remotes(remotes, update=update, check_updates=check_update)

        assert profile_host is not None
        assert profile_build is not None

        builder = DepsGraphBuilder(app.proxy, app.loader, app.range_resolver)
        deps_graph = builder.load_graph(root_node, profile_host, profile_build, lockfile)

        if lockfile:
            lockfile.update_lock(deps_graph)

        return deps_graph

    @api_method
    def analyze_binaries(self, graph, build_mode=None, remotes=None, update=None, lockfile=None):
        """ Given a dependency graph, will compute the package_ids of all recipes in the graph, and
        evaluate if they should be built from sources, downloaded from a remote server, of if the
        packages are already in the local Conan cache
        :param lockfile:
        :param graph: a Conan dependency graph, as returned by "load_graph()"
        :param build_mode: TODO: Discuss if this should be a BuildMode object or list of arguments
        :param remotes: list of remotes
        :param update: (False by default), if Conan should look for newer versions or revisions for
                       already existing recipes in the Conan cache
        """
        conan_app = ConanApp(self.conan_api.cache_folder)
        conan_app.load_remotes(remotes, update=update)
        graph.report_graph_error()
        binaries_analyzer = GraphBinariesAnalyzer(conan_app)
        binaries_analyzer.evaluate_graph(graph, build_mode, lockfile)
