# coding=utf-8

import textwrap

from conans.model.profile import Profile
from conans.util.files import save
from conans.test.functional.graph.graph_manager_base import GraphManagerTest

from conans.model.graph_info import GraphInfo


class ClassicProtocExample(GraphManagerTest):
    """ There is an application that requires the protobuf library, and also
        build_requires the protoc executable to generate some files, but protoc
        also requires the protobuf library to build.

        Expected packages:
            * host_machine: application, protobuf
            * build_machine: protoc, protobuf
    """

    protobuf = textwrap.dedent("""
        from conans import ConanFile
        
        class Protobuf(ConanFile):
            name = "protobuf"
            version = "testing"
            
            settings = "os"  # , "arch", "compiler", "build_type"
            
            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    protoc = textwrap.dedent("""
        from conans import ConanFile
        
        class Protoc(ConanFile):
            name = "protoc"
            version = "testing"
            
            settings = "os"
            requires = "protobuf/testing@user/channel"
            
            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    application = textwrap.dedent("""
                from conans import ConanFile
        
        class Protoc(ConanFile):
            name = "application"
            version = "testing"
            
            settings = "os"
            build_requires = "protoc/testing@user/channel"
            
            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    settings_yml = textwrap.dedent("""
        os:
            Host:
            Build:
    """)

    def setUp(self):
        super(ClassicProtocExample, self).setUp()
        self._cache_recipe("protobuf/testing@user/channel", self.protobuf)
        self._cache_recipe("protoc/testing@user/channel", self.protoc)
        self._cache_recipe("application/testing@user/channel", self.application)

        save(self.cache.settings_path, self.settings_yml)

    def test_something(self):
        profile_host = Profile()
        profile_host.settings["os"] = "Host"
        profile_host.process_settings(self.cache)

        profile_build = Profile()
        profile_build.settings["os"] = "Build"
        profile_build.process_settings(self.cache)

        graph_info = GraphInfo(profile, options, root_ref=ref)

        deps_graph, _ = self.manager.load_graph(path, create_ref, graph_info,
                                                build_mode, check_updates, update,
                                                remotes, recorder)

        """        
        path = temp_folder()
        path = os.path.join(path, "conanfile.py")
        save(path, str(content))
        self.loader.cached_conanfiles = {}

        profile = Profile()
        if profile_build_requires:
            profile.build_requires = profile_build_requires
        profile.process_settings(self.cache)
        update = check_updates = False
        recorder = ActionRecorder()
        remotes = Remotes()
        build_mode = []
        ref = ref or ConanFileReference(None, None, None, None, validate=False)
        options = OptionsValues()
        graph_info = GraphInfo(profile, options, root_ref=ref)
        deps_graph, _ = self.manager.load_graph(path, create_ref, graph_info,
                                                build_mode, check_updates, update,
                                                remotes, recorder)
        self.binary_installer.install(deps_graph, False, graph_info)
        return deps_graph
        """
