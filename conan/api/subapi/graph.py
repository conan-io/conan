from conan.api.output import ConanOutput
from conan.internal.conan_app import ConanApp
from conans.client.graph.graph import Node, RECIPE_CONSUMER, CONTEXT_HOST, RECIPE_VIRTUAL, \
    CONTEXT_BUILD
from conans.client.graph.graph_binaries import GraphBinariesAnalyzer
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.client.graph.profile_node_definer import initialize_conanfile_profile, consumer_definer
from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference


class GraphAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def _load_root_consumer_conanfile(self, path, profile_host, profile_build,
                                      name=None, version=None, user=None, channel=None,
                                      update=None, remotes=None, lockfile=None,
                                      is_build_require=False):
        app = ConanApp(self.conan_api.cache_folder)

        if path.endswith(".py"):
            conanfile = app.loader.load_consumer(path,
                                                 name=name,
                                                 version=version,
                                                 user=user,
                                                 channel=channel,
                                                 graph_lock=lockfile,
                                                 remotes=remotes,
                                                 update=update)
            ref = RecipeReference(conanfile.name, conanfile.version,
                                  conanfile.user, conanfile.channel)
            context = CONTEXT_BUILD if is_build_require else CONTEXT_HOST
            # Here, it is always the "host" context because it is the base, not the current node one
            initialize_conanfile_profile(conanfile, profile_build, profile_host, CONTEXT_HOST,
                                         is_build_require, ref)
            if ref.name:
                profile_host.options.scope(ref)
            root_node = Node(ref, conanfile, context=context, recipe=RECIPE_CONSUMER, path=path)
            root_node.should_build = True  # It is a consumer, this is something we are building
        else:
            conanfile = app.loader.load_conanfile_txt(path)
            consumer_definer(conanfile, profile_host, profile_build)
            root_node = Node(None, conanfile, context=CONTEXT_HOST, recipe=RECIPE_CONSUMER,
                             path=path)
        return root_node

    def load_root_test_conanfile(self, path, tested_reference, profile_host, profile_build,
                                 update=None, remotes=None, lockfile=None,
                                 tested_python_requires=None):
        """ Create and initialize a root node from a test_package/conanfile.py consumer

        :param tested_python_requires: the reference of the ``python_require`` to be tested
        :param lockfile: Might be good to lock python-requires, build-requires
        :param path: The full path to the test_package/conanfile.py being used
        :param tested_reference: The full RecipeReference of the tested package
        :param profile_host:
        :param profile_build:
        :param update:
        :param remotes:
        :return: a graph Node, recipe=RECIPE_CONSUMER
        """

        app = ConanApp(self.conan_api.cache_folder)
        # necessary for correct resolution and update of remote python_requires

        loader = app.loader
        profile_host.options.scope(tested_reference)

        # do not try apply lock_python_requires for test_package/conanfile.py consumer
        conanfile = loader.load_consumer(path, user=tested_reference.user,
                                         channel=tested_reference.channel,
                                         graph_lock=lockfile, remotes=remotes,
                                         tested_python_requires=tested_python_requires,
                                         update=update)
        initialize_conanfile_profile(conanfile, profile_build, profile_host, CONTEXT_HOST, False)
        conanfile.display_name = "%s (test package)" % str(tested_reference)
        conanfile.output.scope = conanfile.display_name
        conanfile.tested_reference_str = repr(tested_reference)

        ref = RecipeReference(conanfile.name, conanfile.version, tested_reference.user,
                              tested_reference.channel)
        root_node = Node(ref, conanfile, recipe=RECIPE_CONSUMER, context=CONTEXT_HOST, path=path)
        return root_node

    def _load_root_virtual_conanfile(self, profile_host, profile_build, requires, tool_requires,
                                     lockfile, remotes, update, check_updates=False, python_requires=None):
        if not python_requires and not requires and not tool_requires:
            raise ConanException("Provide requires or tool_requires")
        app = ConanApp(self.conan_api.cache_folder)
        conanfile = app.loader.load_virtual(requires=requires,
                                            tool_requires=tool_requires,
                                            python_requires=python_requires,
                                            graph_lock=lockfile, remotes=remotes,
                                            update=update, check_updates=check_updates)

        consumer_definer(conanfile, profile_host, profile_build)
        root_node = Node(ref=None, conanfile=conanfile, context=CONTEXT_HOST, recipe=RECIPE_VIRTUAL)
        return root_node

    @staticmethod
    def _scope_options(profile, requires, tool_requires):
        """
        Command line helper to scope options when ``command -o myoption=myvalue`` is used,
        that needs to be converted to "-o pkg:myoption=myvalue". The "pkg" value will be
        computed from the given requires/tool_requires
        """
        # FIXME: This helper function here is not great, find a better place
        if requires and len(requires) == 1 and not tool_requires:
            profile.options.scope(requires[0])
        if tool_requires and len(tool_requires) == 1 and not requires:
            profile.options.scope(tool_requires[0])

    def load_graph_requires(self, requires, tool_requires, profile_host, profile_build,
                            lockfile, remotes, update, check_updates=False, python_requires=None):
        requires = [RecipeReference.loads(r) if isinstance(r, str) else r for r in requires] \
            if requires else None
        tool_requires = [RecipeReference.loads(r) if isinstance(r, str) else r
                         for r in tool_requires] if tool_requires else None

        self._scope_options(profile_host, requires=requires, tool_requires=tool_requires)
        root_node = self._load_root_virtual_conanfile(requires=requires, tool_requires=tool_requires,
                                                      profile_host=profile_host,
                                                      profile_build=profile_build,
                                                      lockfile=lockfile, remotes=remotes,
                                                      update=update,
                                                      python_requires=python_requires)

        # check_updates = args.check_updates if "check_updates" in args else False
        deps_graph = self.load_graph(root_node, profile_host=profile_host,
                                     profile_build=profile_build,
                                     lockfile=lockfile,
                                     remotes=remotes,
                                     update=update,
                                     check_update=check_updates)
        return deps_graph

    def load_graph_consumer(self, path, name, version, user, channel,
                            profile_host, profile_build, lockfile, remotes, update,
                            check_updates=False, is_build_require=False):
        root_node = self._load_root_consumer_conanfile(path, profile_host, profile_build,
                                                       name=name, version=version, user=user,
                                                       channel=channel, lockfile=lockfile,
                                                       remotes=remotes, update=update,
                                                       is_build_require=is_build_require)

        deps_graph = self.load_graph(root_node, profile_host=profile_host,
                                     profile_build=profile_build, lockfile=lockfile,
                                     remotes=remotes, update=update, check_update=check_updates)
        return deps_graph

    def load_graph(self, root_node, profile_host, profile_build, lockfile=None, remotes=None,
                   update=False, check_update=False):
        """ Compute the dependency graph, starting from a root package, evaluation the graph with
        the provided configuration in profile_build, and profile_host. The resulting graph is a
        graph of recipes, but packages are not computed yet (package_ids) will be empty in the
        result. The result might have errors, like version or configuration conflicts, but it is still
        possible to inspect it. Only trying to install such graph will fail

        :param root_node: the starting point, an already initialized Node structure, as
            returned by the "load_root_node" api
        :param profile_host: The host profile
        :param profile_build: The build profile
        :param lockfile: A valid lockfile (None by default, means no locked)
        :param remotes: list of remotes we want to check
        :param update: (False by default), if Conan should look for newer versions or
            revisions for already existing recipes in the Conan cache
        :param check_update: For "graph info" command, check if there are recipe updates
        """
        ConanOutput().title("Computing dependency graph")
        app = ConanApp(self.conan_api.cache_folder)

        assert profile_host is not None
        assert profile_build is not None

        remotes = remotes or []
        builder = DepsGraphBuilder(app.proxy, app.loader, app.range_resolver, app.cache, remotes,
                                   update, check_update)
        deps_graph = builder.load_graph(root_node, profile_host, profile_build, lockfile)
        return deps_graph

    def analyze_binaries(self, graph, build_mode=None, remotes=None, update=None, lockfile=None,
                         build_modes_test=None, tested_graph=None):
        """ Given a dependency graph, will compute the package_ids of all recipes in the graph, and
        evaluate if they should be built from sources, downloaded from a remote server, of if the
        packages are already in the local Conan cache

        :param lockfile:
        :param graph: a Conan dependency graph, as returned by "load_graph()"
        :param build_mode: TODO: Discuss if this should be a BuildMode object or list of arguments
        :param remotes: list of remotes
        :param update: (False by default), if Conan should look for newer versions or
            revisions for already existing recipes in the Conan cache
        :param build_modes_test: the --build-test argument
        :param tested_graph: In case of a "test_package", the graph being tested
        """
        ConanOutput().title("Computing necessary packages")
        conan_app = ConanApp(self.conan_api.cache_folder)
        binaries_analyzer = GraphBinariesAnalyzer(conan_app)
        binaries_analyzer.evaluate_graph(graph, build_mode, lockfile, remotes, update,
                                         build_modes_test, tested_graph)
