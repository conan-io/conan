# coding=utf-8

import os
import textwrap

from parameterized.parameterized import parameterized

from conans.client.cache.remote_registry import Remotes
from conans.client.graph.graph import CONTEXT_BUILD, CONTEXT_HOST
from conans.client.recorder.action_recorder import ActionRecorder
from conans.model.graph_info import GraphInfo
from conans.model.options import OptionsValues
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.test.functional.graph.graph_manager_base import GraphManagerTest
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class ClassicProtocExampleBase(GraphManagerTest):
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
                
            def package_info(self):
                protobuf_str = "protobuf-host" if self.settings.os == "Host" else "protobuf-build"

                self.cpp_info.includedirs = [protobuf_str, ]
                self.cpp_info.libdirs = [protobuf_str, ]
                self.cpp_info.bindirs = [protobuf_str, ]
                
                self.env_info.PATH.append(protobuf_str)
                self.env_info.OTHERVAR = protobuf_str
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

            def package_info(self):
                protoc_str = "protoc-host" if self.settings.os == "Host" else "protoc-build"
                
                self.cpp_info.includedirs = [protoc_str, ]
                self.cpp_info.libdirs = [protoc_str, ]
                self.cpp_info.bindirs = [protoc_str, ]
                
                self.env_info.PATH.append(protoc_str)
                self.env_info.OTHERVAR = protoc_str
    """)

    application = textwrap.dedent("""
        from conans import ConanFile
        
        class Protoc(ConanFile):
            name = "application"
            version = "testing"
            
            settings = "os"
            requires = "protobuf/testing@user/channel"
            
            def build_requirements(self):
                self.build_requires("protoc/testing@user/channel")
            
            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    settings_yml = textwrap.dedent("""
        os:
            Host:
            Build:
    """)

    protobuf_ref = ConanFileReference.loads("protobuf/testing@user/channel")
    protoc_ref = ConanFileReference.loads("protoc/testing@user/channel")
    application_ref = ConanFileReference.loads("application/testing@user/channel")

    def setUp(self):
        super(ClassicProtocExampleBase, self).setUp()
        self._cache_recipe(self.protobuf_ref, self.protobuf)
        self._cache_recipe(self.protoc_ref, self.protoc)
        self._cache_recipe(self.application_ref, self.application)

        save(self.cache.settings_path, self.settings_yml)

    def _build_graph(self, profile_host, profile_build):
        path = temp_folder()
        path = os.path.join(path, "conanfile.txt")
        save(path, textwrap.dedent("""
            [requires]
            application/testing@user/channel
        """))

        ref = ConanFileReference(None, None, None, None, validate=False)
        options = OptionsValues()
        graph_info = GraphInfo(profile=profile_host, profile_build=profile_build,
                               options=options, root_ref=ref)

        deps_graph, _ = self.manager.load_graph(path, create_reference=None, graph_info=graph_info,
                                                build_mode=[], check_updates=False, update=False,
                                                remotes=Remotes(), recorder=ActionRecorder())
        if True:
            self.binary_installer.install(deps_graph, None, False, graph_info)
        return deps_graph


class ClassicProtocExample(ClassicProtocExampleBase):

    @parameterized.expand([(True, ), (False, )])
    def test_crossbuilding(self, xbuilding):
        profile_host = Profile()
        profile_host.settings["os"] = "Host"
        profile_host.process_settings(self.cache)

        if xbuilding:
            profile_build = Profile()
            profile_build.settings["os"] = "Build"
            profile_build.process_settings(self.cache)
        else:
            profile_build = None

        deps_graph = self._build_graph(profile_host=profile_host, profile_build=profile_build)

        # Check HOST packages
        #   - application
        application = deps_graph.root.dependencies[0].dst
        self.assertEqual(len(application.dependencies), 2)
        self.assertEqual(application.conanfile.name, "application")
        self.assertEqual(application.context, CONTEXT_HOST)
        self.assertEqual(application.conanfile.settings.os, profile_host.settings['os'])
        if xbuilding:
            # cpp_info:
            protobuf_host_cpp_info = application.conanfile.deps_cpp_info["protobuf"]
            self.assertEqual(protobuf_host_cpp_info.includedirs, ['protobuf-host'])
            self.assertEqual(protobuf_host_cpp_info.libdirs, ['protobuf-host'])
            self.assertEqual(protobuf_host_cpp_info.bindirs, ['protobuf-host'])
            with self.assertRaises(KeyError):
                application.conanfile.deps_cpp_info["protoc"]

            # env_info:
            protoc_env_info = application.conanfile.deps_env_info["protoc"]
            self.assertEqual(protoc_env_info.PATH, ['protoc-build'])
            self.assertEqual(protoc_env_info.OTHERVAR, 'protoc-build')

            protobuf_env_info = application.conanfile.deps_env_info["protobuf"]
            self.assertEqual(protobuf_env_info.PATH, ['protobuf-build'])
            self.assertEqual(protobuf_env_info.OTHERVAR, 'protobuf-build')

        #   - protobuf host
        protobuf_host = application.dependencies[0].dst
        self.assertEqual(protobuf_host.conanfile.name, "protobuf")
        self.assertEqual(protobuf_host.context, CONTEXT_HOST)
        self.assertEqual(protobuf_host.conanfile.settings.os, profile_host.settings['os'])

        # Check BUILD packages (default behavior changes if we use profile_build)
        #   - protoc
        protoc_build = application.dependencies[1].dst
        self.assertEqual(protoc_build.conanfile.name, "protoc")
        self.assertEqual(protoc_build.context, CONTEXT_BUILD if xbuilding else CONTEXT_HOST)
        self.assertEqual(str(protoc_build.conanfile.settings.os),
                         (profile_build if xbuilding else profile_host).settings['os'])

        #   - protobuf build
        protobuf_build = protoc_build.dependencies[0].dst
        self.assertEqual(protobuf_build.conanfile.name, "protobuf")
        self.assertEqual(protoc_build.context, CONTEXT_BUILD if xbuilding else CONTEXT_HOST)
        self.assertEqual(str(protobuf_build.conanfile.settings.os),
                         (profile_build if xbuilding else profile_host).settings['os'])


