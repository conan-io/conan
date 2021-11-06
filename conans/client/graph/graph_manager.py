
import os
import traceback

from conans.cli.output import ConanOutput
from conans.client.conanfile.configure import run_configure_method
from conans.client.graph.graph import Node, CONTEXT_HOST
from conans.client.graph.graph_binaries import RECIPE_CONSUMER, RECIPE_VIRTUAL
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.client.profile_loader import ProfileLoader
from conans.model.options import Options
from conans.model.ref import ConanFileReference


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
        profile_host = profile_loader.from_cli_args(None, None, None, None, None, os.getcwd())

        name, version, user, channel = None, None, None, None
        if conanfile_path.endswith(".py"):
            # The global.conf is necessary for download_cache definition
            profile_host.conf.rebase_conf_definition(self._cache.new_config)
            conanfile = self._loader.load_consumer(conanfile_path,
                                                   profile_host=profile_host,
                                                   name=name, version=version,
                                                   user=user, channel=channel,
                                                   graph_lock=None)

            run_configure_method(conanfile, down_options=Options(),
                                 profile_options=profile_host.options,  ref=None)
        else:
            conanfile = self._loader.load_conanfile_txt(conanfile_path, profile_host=profile_host)

        return conanfile

    def load_graph(self, reference, create_reference, profile_host, profile_build, graph_lock,
                   root_ref, build_mode, is_build_require=False, require_overrides=None):
        """ main entry point to compute a full dependency graph
        """
        assert profile_host is not None
        assert profile_build is not None

        root_node = self._load_root_node(reference, create_reference, profile_host, graph_lock,
                                         root_ref, is_build_require,
                                         require_overrides)
        profile_host_build_requires = profile_host.build_requires
        builder = DepsGraphBuilder(self._proxy, self._loader, self._range_resolver)
        deps_graph = builder.load_graph(root_node, profile_host, profile_build, graph_lock)
        version_ranges_output = self._range_resolver.output
        if version_ranges_output:
            self._output.success("Version ranges solved")
            for msg in version_ranges_output:
                self._output.info("    %s" % msg)
            self._output.writeln("")
            self._range_resolver.clear_output()

        # TODO: Move binary_analyzer elsewhere
        if not deps_graph.error:
            self._binaries_analyzer.evaluate_graph(deps_graph, build_mode)

        return deps_graph

    def _load_root_node(self, reference, create_reference, profile_host, graph_lock, root_ref,
                        is_build_require, require_overrides):
        """ creates the first, root node of the graph, loading or creating a conanfile
        and initializing it (settings, options) as necessary. Also locking with lockfile
        information
        """
        profile_host.dev_reference = create_reference  # Make sure the created one has develop=True

        # create (without test_package), install|info|graph|export-pkg <ref>
        if isinstance(reference, ConanFileReference):
            # options without scope like ``-o shared=True`` refer to this reference
            profile_host.options.scope(reference.name)
            # FIXME: Might need here the profile_build
            return self._load_root_direct_reference(reference, profile_host,
                                                    is_build_require,
                                                    require_overrides)

        path = reference  # The reference must be pointing to a user space conanfile
        if create_reference:  # Test_package -> tested reference
            profile_host.options.scope(create_reference.name)
            return self._load_root_test_package(path, create_reference, graph_lock, profile_host,
                                                require_overrides)

        # It is a path to conanfile.py or conanfile.txt
        root_node = self._load_root_consumer(path, graph_lock, profile_host, root_ref,
                                             require_overrides)
        return root_node

    def _load_root_consumer(self, path, graph_lock, profile, ref, require_overrides):
        """ load a CONSUMER node from a user space conanfile.py or conanfile.txt
        install|info|create|graph <path>
        :path full path to a conanfile
        :graph_lock: might be None, information of lockfiles
        :profile: data to inject to the consumer node: settings, options
        :ref: previous reference of a previous command. Can be used for finding itself in
              the lockfile, or to initialize
        """
        if path.endswith(".py"):
            conanfile = self._loader.load_consumer(path, profile,
                                                   name=ref.name,
                                                   version=ref.version,
                                                   user=ref.user,
                                                   channel=ref.channel,
                                                   graph_lock=graph_lock,
                                                   require_overrides=require_overrides)

            ref = ConanFileReference(conanfile.name, conanfile.version,
                                     ref.user, ref.channel, validate=False)
            if ref.name:
                profile.options.scope(ref.name)
            root_node = Node(ref, conanfile, context=CONTEXT_HOST, recipe=RECIPE_CONSUMER, path=path)
        else:
            conanfile = self._loader.load_conanfile_txt(path, profile, ref=ref)
            root_node = Node(None, conanfile, context=CONTEXT_HOST, recipe=RECIPE_CONSUMER,
                             path=path)

        return root_node

    def _load_root_direct_reference(self, reference, profile,
                                    is_build_require, require_overrides):
        """ When a full reference is provided:
        install|info|graph <ref> or export-pkg .
        :return a VIRTUAL root_node with a conanfile that requires the reference
        """
        conanfile = self._loader.load_virtual([reference], profile,
                                              is_build_require=is_build_require,
                                              require_overrides=require_overrides)
        root_node = Node(ref=None, conanfile=conanfile, context=CONTEXT_HOST, recipe=RECIPE_VIRTUAL)
        return root_node

    def _load_root_test_package(self, path, create_reference, graph_lock, profile,
                                require_overrides):
        """ when a test_package/conanfile.py is provided, together with the reference that is
        being created and need to be tested
        :return a CONSUMER root_node with a conanfile.py with an injected requires to the
        created reference
        """
        test = str(create_reference)
        # do not try apply lock_python_requires for test_package/conanfile.py consumer
        conanfile = self._loader.load_consumer(path, profile, user=create_reference.user,
                                               channel=create_reference.channel,
                                               require_overrides=require_overrides
                                               )
        conanfile.display_name = "%s (test package)" % str(test)
        conanfile.output.scope = conanfile.display_name

        # Injection of the tested reference
        test_type = getattr(conanfile, "test_type", ("requires", ))
        if not isinstance(test_type, (list, tuple)):
            test_type = (test_type, )
        if "build_requires" in test_type:
            conanfile.requires.build_require(str(create_reference))
        if "requires" in test_type:
            require = False # conanfile.requires.get(create_reference.name)
            if require:
                require.ref = require.range_ref = create_reference
            else:
                conanfile.requires(repr(create_reference))

        ref = ConanFileReference(conanfile.name, conanfile.version,
                                 create_reference.user, create_reference.channel, validate=False)
        root_node = Node(ref, conanfile, recipe=RECIPE_CONSUMER, context=CONTEXT_HOST, path=path)
        return root_node
