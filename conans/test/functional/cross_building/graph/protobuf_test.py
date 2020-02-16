# coding=utf-8

import os
import textwrap

from conans.client.cache.remote_registry import Remotes
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.graph import CONTEXT_BUILD, CONTEXT_HOST
from conans.client.installer import BinaryInstaller
from conans.client.recorder.action_recorder import ActionRecorder
from conans.model.graph_info import GraphInfo
from conans.model.options import OptionsValues
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.test.functional.graph.graph_manager_base import GraphManagerTest
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class ProtobufTest(GraphManagerTest):

    zlib = textwrap.dedent("""
        from conans import ConanFile

        class Zlib(ConanFile):
            settings = "os"
            
            def package_info(self):
                zlib_str = "zlib-host" if self.settings.os == "Host" else "zlib-build"
                zlib_str += str(self.version)

                self.cpp_info.libs = [zlib_str, ]
                
                self.env_info.PATH.append(zlib_str)
                self.env_info.OTHERVAR = zlib_str
        """)
    bzip = textwrap.dedent("""
        from conans import ConanFile

        class Bzip2(ConanFile):
            settings = "os"

            def package_info(self):
                zlib_str = "bzip-host" if self.settings.os == "Host" else "bzip-build"
                zlib_str += str(self.version)

                self.cpp_info.libs = [zlib_str, ]

                self.env_info.PATH.append(zlib_str)
                self.env_info.OTHERVAR = zlib_str
        """)

    protobuf = textwrap.dedent("""
        from conans import ConanFile
        
        class Protobuf(ConanFile):
            settings = "os"
            def requirements(self):
                if self.settings.os == "Host":
                    self.requires("zlib/1.0@user/channel")
                else:
                    self.requires("zlib/2.0@user/channel")
            
            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
                self.output.info("ZLIB: %s" % self.deps_cpp_info["zlib"].libs)
                
            def package_info(self):
                protobuf_str = "protobuf-host" if self.settings.os == "Host" else "protobuf-build"

                self.cpp_info.includedirs = [protobuf_str, ]
                self.cpp_info.libdirs = [protobuf_str, ]
                self.cpp_info.bindirs = [protobuf_str, ]
                self.cpp_info.libs = [protobuf_str]
                
                self.env_info.PATH.append(protobuf_str)
                self.env_info.OTHERVAR = protobuf_str
        """)

    app = textwrap.dedent("""
        from conans import ConanFile
        
        class App(ConanFile):
            settings = "os"
            requires = "protobuf/testing@user/channel"
            build_requires = "protobuf/testing@user/channel"
            
            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
                self.output.info("ZLIB: %s" % self.deps_cpp_info["zlib"].libs)
        """)

    cmake = textwrap.dedent("""
        from conans import ConanFile

        class CMake(ConanFile):
            settings = "os"
            requires = "bzip/3.0@user/channel"

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
                self.output.info("BZIP: %s" % self.deps_cpp_info["bzip"].libs)

            def package_info(self):
                assert self.settings.os == "Build"

                self.env_info.PATH.append("cmake_build")
                self.env_info.OTHERVAR = "cmake_build"
        """)

    settings_yml = textwrap.dedent("""
        os:
            Host:
            Build:
    """)

    zlib1_ref = ConanFileReference.loads("zlib/1.0@user/channel")
    zlib2_ref = ConanFileReference.loads("zlib/2.0@user/channel")
    bzip_ref = ConanFileReference.loads("bzip/3.0@user/channel")
    cmake_ref = ConanFileReference.loads("cmake/3.14@user/channel")
    protobuf_ref = ConanFileReference.loads("protobuf/testing@user/channel")
    app_ref = ConanFileReference.loads("app/testing@user/channel")

    def setUp(self):
        super(ProtobufTest, self).setUp()
        self._cache_recipe(self.zlib1_ref, self.zlib)
        self._cache_recipe(self.zlib2_ref, self.zlib)
        self._cache_recipe(self.bzip_ref, self.bzip)
        self._cache_recipe(self.cmake_ref, self.cmake)
        self._cache_recipe(self.protobuf_ref, self.protobuf)
        self._cache_recipe(self.app_ref, self.app)

        save(self.cache.settings_path, self.settings_yml)

    def _build_graph(self, profile_host, profile_build):
        path = temp_folder()
        path = os.path.join(path, "conanfile.txt")
        save(path, textwrap.dedent("""
            [requires]
            app/testing@user/channel
        """))

        ref = ConanFileReference(None, None, None, None, validate=False)
        options = OptionsValues()
        graph_info = GraphInfo(profile_host=profile_host, profile_build=profile_build,
                               options=options, root_ref=ref)
        recorder = ActionRecorder()
        app = self._get_app()
        deps_graph = app.graph_manager.load_graph(path, create_reference=None, graph_info=graph_info,
                                                  build_mode=[], check_updates=False, update=False,
                                                  remotes=Remotes(), recorder=recorder)

        build_mode = []  # Means build all
        binary_installer = BinaryInstaller(app, recorder)
        build_mode = BuildMode(build_mode, app.out)
        binary_installer.install(deps_graph, None, build_mode, update=False,
                                 keep_build=False, graph_info=graph_info)
        return deps_graph

    def test_crossbuilding(self):
        profile_host = Profile()
        profile_host.settings["os"] = "Host"
        profile_host.process_settings(self.cache)

        profile_build = Profile()
        profile_build.settings["os"] = "Build"
        profile_build.process_settings(self.cache)

        deps_graph = self._build_graph(profile_host=profile_host, profile_build=profile_build)

        # Check HOST packages
        #   - app
        app = deps_graph.root.dependencies[0].dst
        self.assertEqual(len(app.dependencies), 2)
        self.assertEqual(app.conanfile.name, "app")
        self.assertEqual(app.context, CONTEXT_HOST)
        self.assertEqual(app.conanfile.settings.os, profile_host.settings['os'])

        # App deps_cpp_info
        protobuf_host_cpp_info = app.conanfile.deps_cpp_info["protobuf"]
        self.assertEqual(protobuf_host_cpp_info.includedirs, ['protobuf-host'])
        self.assertEqual(protobuf_host_cpp_info.libdirs, ['protobuf-host'])
        self.assertEqual(protobuf_host_cpp_info.bindirs, ['protobuf-host'])
        protobuf_host_cpp_info = app.conanfile.deps_cpp_info["zlib"]
        self.assertEqual(protobuf_host_cpp_info.libs, ['zlib-host1.0'])
        self.assertEqual(app.conanfile.deps_cpp_info.libs, ['protobuf-host', 'zlib-host1.0'])

        # App deps_env_info
        protobuf_env_info = app.conanfile.deps_env_info["protobuf"]
        self.assertEqual(protobuf_env_info.PATH, ['protobuf-build'])
        self.assertEqual(protobuf_env_info.OTHERVAR, 'protobuf-build')
        zlib_env_info = app.conanfile.deps_env_info["zlib"]
        self.assertEqual(zlib_env_info.vars["PATH"], ['zlib-build2.0'])
        self.assertEqual(app.conanfile.deps_env_info.vars["PATH"],
                         ['protobuf-build', 'zlib-build2.0'])

        # Protobuf Host
        protobuf_host = app.dependencies[0].dst
        self.assertEqual(protobuf_host.conanfile.name, "protobuf")
        self.assertEqual(protobuf_host.context, CONTEXT_HOST)
        self.assertEqual(protobuf_host.conanfile.settings.os, "Host")

        # Protobuf Host deps_cpp_info
        zlib_cpp_info = protobuf_host.conanfile.deps_cpp_info["zlib"]
        self.assertEqual(zlib_cpp_info.libs, ['zlib-host1.0'])

        # Protobuf Host has NO deps_env_info for zlib
        zlib_env_info = list(protobuf_host.conanfile.deps_env_info.deps)
        self.assertEqual(zlib_env_info, [])

        # Protobuf Build
        protobuf_build = app.dependencies[1].dst
        self.assertEqual(protobuf_build.conanfile.name, "protobuf")
        self.assertEqual(protobuf_build.context, CONTEXT_BUILD)
        self.assertEqual(protobuf_build.conanfile.settings.os, "Build")

        # Protobuf Build deps_cpp_info
        zlib_cpp_info = protobuf_build.conanfile.deps_cpp_info["zlib"]
        self.assertEqual(zlib_cpp_info.libs, ['zlib-build2.0'])

        # Protobuf Build has NO deps_env_info from zlib
        zlib_env_info = list(protobuf_build.conanfile.deps_env_info.deps)
        self.assertEqual(zlib_env_info, [])

    def test_crossbuilding_with_build_require_cmake(self):
        profile_host = Profile()
        profile_host.settings["os"] = "Host"
        profile_host.process_settings(self.cache)
        profile_host.build_requires["*"] = [self.cmake_ref]

        profile_build = Profile()
        profile_build.settings["os"] = "Build"
        profile_build.process_settings(self.cache)
        profile_build.build_requires["*"] = [self.cmake_ref]
        profile_build.build_requires["zlib/3.0*"] = []

        deps_graph = self._build_graph(profile_host=profile_host, profile_build=profile_build)

        # Check HOST packages
        #   - app
        app = deps_graph.root.dependencies[0].dst
        self.assertEqual(len(app.dependencies), 3)
        self.assertEqual(app.conanfile.name, "app")
        self.assertEqual(app.context, CONTEXT_HOST)
        self.assertEqual(app.conanfile.settings.os, "Host")

        # App deps_cpp_info
        protobuf_host_cpp_info = app.conanfile.deps_cpp_info["protobuf"]
        self.assertEqual(protobuf_host_cpp_info.includedirs, ['protobuf-host'])
        self.assertEqual(protobuf_host_cpp_info.libdirs, ['protobuf-host'])
        self.assertEqual(protobuf_host_cpp_info.bindirs, ['protobuf-host'])
        zlib_host_cpp_info = app.conanfile.deps_cpp_info["zlib"]
        self.assertEqual(zlib_host_cpp_info.libs, ['zlib-host1.0'])
        self.assertEqual(app.conanfile.deps_cpp_info.libs, ['protobuf-host', 'zlib-host1.0'])

        # App deps_env_info
        protobuf_env_info = app.conanfile.deps_env_info["protobuf"]
        self.assertEqual(protobuf_env_info.PATH, ['protobuf-build'])
        self.assertEqual(protobuf_env_info.OTHERVAR, 'protobuf-build')
        zlib_env_info = app.conanfile.deps_env_info["zlib"]
        self.assertEqual(zlib_env_info.vars["PATH"], ['zlib-build2.0'])
        self.assertEqual(app.conanfile.deps_env_info.vars["PATH"],
                         ['cmake_build', 'protobuf-build', 'bzip-build3.0', 'zlib-build2.0'])

        # Protobuf Host
        protobuf_host = app.dependencies[0].dst
        self.assertEqual(protobuf_host.conanfile.name, "protobuf")
        self.assertEqual(protobuf_host.context, CONTEXT_HOST)
        self.assertEqual(protobuf_host.conanfile.settings.os, "Host")

        # Protobuf Host deps_cpp_info
        zlib_cpp_info = protobuf_host.conanfile.deps_cpp_info["zlib"]
        self.assertEqual(zlib_cpp_info.libs, ['zlib-host1.0'])
        self.assertEqual(protobuf_host.conanfile.deps_cpp_info.libs, ['zlib-host1.0'])

        # Protobuf Host has NO deps_env_info for zlib
        zlib_env_info = list(protobuf_host.conanfile.deps_env_info.deps)
        self.assertEqual(zlib_env_info, ['cmake', 'bzip'])
        self.assertEqual(protobuf_host.conanfile.deps_env_info.vars["PATH"],
                         ['cmake_build', 'bzip-build3.0'])

        # zlib host
        zlib_host = protobuf_host.dependencies[0].dst
        self.assertEqual(zlib_host.conanfile.name, "zlib")
        self.assertEqual(zlib_host.context, CONTEXT_HOST)
        self.assertEqual(zlib_host.conanfile.settings.os, "Host")
        self.assertEqual(zlib_host.conanfile.deps_cpp_info.libs, [])
        self.assertEqual(zlib_host.conanfile.deps_env_info.vars["PATH"],
                         ['cmake_build', 'bzip-build3.0'])

        # Protobuf Build
        protobuf_build = app.dependencies[1].dst
        self.assertEqual(protobuf_build.conanfile.name, "protobuf")
        self.assertEqual(protobuf_build.context, CONTEXT_BUILD)
        self.assertEqual(protobuf_build.conanfile.settings.os, "Build")

        # Protobuf Build deps_cpp_info
        zlib_cpp_info = protobuf_build.conanfile.deps_cpp_info["zlib"]
        self.assertEqual(zlib_cpp_info.libs, ['zlib-build2.0'])
        self.assertEqual(protobuf_build.conanfile.deps_cpp_info.libs, ['zlib-build2.0'])

        # Protobuf Build has NO deps_env_info from zlib
        zlib_env_info = list(protobuf_build.conanfile.deps_env_info.deps)
        self.assertEqual(zlib_env_info, ['cmake', 'bzip'])
        self.assertEqual(protobuf_build.conanfile.deps_env_info.vars["PATH"],
                         ['cmake_build', 'bzip-build3.0'])
