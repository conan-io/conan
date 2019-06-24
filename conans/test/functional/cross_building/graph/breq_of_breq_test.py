# coding=utf-8

import os
import textwrap

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


class BuildRequireOfBuildRequire(GraphManagerTest):
    """ There is an application that build_requires two different tools:
         * cmake (build)
         * gtest (host), that build_requires 'cmake'
    """

    cmake = textwrap.dedent("""
        from conans import ConanFile

        class BuildRequiresLibrary(ConanFile):
            name = "cmake"
            version = "testing"

            settings = "os"

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    gtest = textwrap.dedent("""
        from conans import ConanFile

        class BuildRequires(ConanFile):
            name = "gtest"
            version = "testing"

            settings = "os"
            
            def build_requirements(self):
                self.build_requires("cmake/testing@user/channel", context="build")

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    application = textwrap.dedent("""
        from conans import ConanFile

        class Application(ConanFile):
            name = "application"
            version = "testing"

            settings = "os"

            def build_requirements(self):
                self.build_requires("cmake/testing@user/channel", context="build")
                self.build_requires("gtest/testing@user/channel", context="host")

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    settings_yml = textwrap.dedent("""
        os:
            Host:
            Build:
    """)

    def setUp(self):
        super(BuildRequireOfBuildRequire, self).setUp()
        self._cache_recipe("cmake/testing@user/channel", self.cmake)
        self._cache_recipe("gtest/testing@user/channel", self.gtest)
        self._cache_recipe("application/testing@user/channel", self.application)

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
        graph_info = GraphInfo(profile_build=profile_build, profile_host=profile_host,
                               options=options, root_ref=ref)

        deps_graph, _ = self.manager.load_graph(path, create_reference=None, graph_info=graph_info,
                                                build_mode=[], check_updates=False, update=False,
                                                remotes=Remotes(), recorder=ActionRecorder())
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
        application = deps_graph.root.dependencies[0].dst
        self.assertEqual(len(application.dependencies), 2)
        self.assertEqual(application.conanfile.name, "application")
        self.assertEqual(application.build_context, CONTEXT_HOST)
        self.assertEqual(application.conanfile.settings.os, profile_host.settings['os'])

        gtest_host = application.dependencies[1].dst
        self.assertEqual(gtest_host.conanfile.name, "gtest")
        self.assertEqual(gtest_host.build_context, CONTEXT_HOST)
        self.assertEqual(gtest_host.conanfile.settings.os, profile_host.settings['os'])

        # Check BUILD packages
        cmake_build = application.dependencies[0].dst
        self.assertEqual(cmake_build.conanfile.name, "cmake")
        self.assertEqual(cmake_build.build_context, CONTEXT_BUILD)
        self.assertEqual(str(cmake_build.conanfile.settings.os), profile_build.settings['os'])

        cmake_gtest_build = gtest_host.dependencies[0].dst
        self.assertNotEqual(cmake_build, cmake_gtest_build)
        self.assertEqual(cmake_gtest_build.conanfile.name, "cmake")
        self.assertEqual(cmake_gtest_build.build_context, CONTEXT_BUILD)
        self.assertEqual(str(cmake_gtest_build.conanfile.settings.os), profile_build.settings['os'])

