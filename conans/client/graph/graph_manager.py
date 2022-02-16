import os

from conans.cli.output import ConanOutput
from conans.client.conanfile.configure import run_configure_method
from conans.client.graph.graph import Node, CONTEXT_HOST
from conans.client.graph.graph_binaries import RECIPE_CONSUMER, RECIPE_VIRTUAL
from conans.client.graph.graph_builder import DepsGraphBuilder

from conans.client.graph.profile_node_definer import txt_definer, virtual_definer, \
    initialize_conanfile_profile
from conans.client.profile_loader import ProfileLoader
from conans.model.options import Options
from conans.model.recipe_ref import RecipeReference


class GraphManager(object):
    def __init__(self, conan_app):
        self._conan_app = conan_app
        self._proxy = conan_app.proxy
        self._output = ConanOutput()
        self._range_resolver = conan_app.range_resolver
        self._cache = conan_app.cache
        self._loader = conan_app.loader
        self._binaries_analyzer = conan_app.binaries_analyzer

    def load_consumer_conanfile(self, conanfile_path):
        """loads a conanfile for local flow: source
        """
        # This is very dirty, should be removed for Conan 2.0 (source() method only)
        # FIXME: Make "conan source" build the whole graph. Do it in another PR
        profile_loader = ProfileLoader(self._cache)
        profiles = [profile_loader.get_default_host()]
        profile_host = profile_loader.from_cli_args(profiles, None, None, None, None, os.getcwd())

        name, version, user, channel = None, None, None, None
        if conanfile_path.endswith(".py"):
            # The global.conf is necessary for download_cache definition
            profile_host.conf.rebase_conf_definition(self._cache.new_config)
            conanfile = self._loader.load_consumer(conanfile_path,
                                                   name=name, version=version,
                                                   user=user, channel=channel,
                                                   graph_lock=None)

            initialize_conanfile_profile(conanfile, profile_host, profile_host, CONTEXT_HOST,
                                         False)

            run_configure_method(conanfile, down_options=Options(),
                                 profile_options=profile_host.options,  ref=None)

        else:
            conanfile = self._loader.load_conanfile_txt(conanfile_path)
            txt_definer(conanfile, profile_host)
        return conanfile

    def load_graph(self, reference, create_reference, profile_host, profile_build, graph_lock,
                   root_ref, build_mode, is_build_require=False, require_overrides=None):
        """ main entry point to compute a full dependency graph
        """
        assert profile_host is not None
        assert profile_build is not None

        root_node = self._load_root_node(reference, create_reference, profile_build, profile_host,
                                         graph_lock,
                                         root_ref, is_build_require,
                                         require_overrides)
        profile_host_tool_requires = profile_host.tool_requires
        builder = DepsGraphBuilder(self._proxy, self._loader, self._range_resolver)
        deps_graph = builder.load_graph(root_node, profile_host, profile_build, graph_lock)

        # TODO: Move binary_analyzer elsewhere
        if not deps_graph.error:
            self._binaries_analyzer.evaluate_graph(deps_graph, build_mode)

        return deps_graph

    def _load_root_node(self, reference, create_reference, profile_build, profile_host,
                        graph_lock, root_ref,
                        is_build_require, require_overrides):
        # create (without test_package), install|info|graph|export-pkg <ref>
        if isinstance(reference, RecipeReference):
            # options without scope like ``-o shared=True`` refer to this reference
            profile_host.options.scope(reference)
            # FIXME: Might need here the profile_build
            return self._load_root_direct_reference(reference, profile_build, profile_host,
                                                    is_build_require,
                                                    require_overrides)

        path = reference  # The reference must be pointing to a user space conanfile
        if create_reference:  # Test_package -> tested reference
            profile_host.options.scope(create_reference)
            return self._load_root_test_package(path, profile_build, profile_host,
                                                create_reference, require_overrides)


        # It is a path to conanfile.py or conanfile.txt
        root_node = self._load_root_consumer(path, graph_lock, profile_build, profile_host,
                                             root_ref, require_overrides)
        return root_node

    def _load_root_consumer(self, path, graph_lock, profile_build, profile_host, ref,
                            require_overrides):
        """ load a CONSUMER node from a user space conanfile.py or conanfile.txt
        install|info|create|graph <path>
        :path full path to a conanfile
        :graph_lock: might be None, information of lockfiles
        :profile: data to inject to the consumer node: settings, options
        :ref: previous reference of a previous command. Can be used for finding itself in
              the lockfile, or to initialize
        """
        if path.endswith(".py"):
            conanfile = self._loader.load_consumer(path,
                                                   name=ref.name,
                                                   version=ref.version,
                                                   user=ref.user,
                                                   channel=ref.channel,
                                                   graph_lock=graph_lock,
                                                   require_overrides=require_overrides)

            initialize_conanfile_profile(conanfile, profile_build, profile_host, CONTEXT_HOST,
                                         False, ref)

            ref = RecipeReference(conanfile.name, conanfile.version, ref.user, ref.channel)
            if ref.name:
                profile_host.options.scope(ref)
            root_node = Node(ref, conanfile, context=CONTEXT_HOST, recipe=RECIPE_CONSUMER, path=path)
        else:
            conanfile = self._loader.load_conanfile_txt(path, require_overrides=require_overrides)
            txt_definer(conanfile, profile_host)
            root_node = Node(None, conanfile, context=CONTEXT_HOST, recipe=RECIPE_CONSUMER,
                             path=path)

        return root_node

    def _load_root_direct_reference(self, reference, profile_build, profile_host,
                                    is_build_require, require_overrides):
        """ When a full reference is provided:
        install|info|graph <ref> or export-pkg .
        :return a VIRTUAL root_node with a conanfile that requires the reference
        """
        conanfile = self._loader.load_virtual([reference],
                                              is_build_require=is_build_require,
                                              require_overrides=require_overrides)
        virtual_definer(conanfile, profile_host)
        root_node = Node(ref=None, conanfile=conanfile, context=CONTEXT_HOST, recipe=RECIPE_VIRTUAL)
        return root_node

    def _load_root_test_package(self, path, profile_build, profile_host, create_reference,
                                require_overrides):
        """ when a test_package/conanfile.py is provided, together with the reference that is
        being created and need to be tested
        :return a CONSUMER root_node with a conanfile.py with an injected requires to the
        created reference
        """
        test = str(create_reference)
        # do not try apply lock_python_requires for test_package/conanfile.py consumer
        conanfile = self._loader.load_consumer(path, user=create_reference.user,
                                               channel=create_reference.channel,
                                               require_overrides=require_overrides
                                               )
        initialize_conanfile_profile(conanfile, profile_build, profile_host, CONTEXT_HOST,
                                     False)
        conanfile.display_name = "%s (test package)" % str(test)
        conanfile.output.scope = conanfile.display_name
        conanfile.tested_reference_str = repr(create_reference)

        ref = RecipeReference(conanfile.name, conanfile.version, create_reference.user,
                              create_reference.channel)
        root_node = Node(ref, conanfile, recipe=RECIPE_CONSUMER, context=CONTEXT_HOST, path=path)
        return root_node
