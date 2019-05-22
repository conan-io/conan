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


class OptionsSpecifiedInRecipes(GraphManagerTest):
    """ An application that build_requires the same tool for different build context, and there
        are some options declared in the recipes for this tool
    """

    gtest = textwrap.dedent("""
        from conans import ConanFile

        class GTest(ConanFile):
            name = "gtest"
            version = "testing"

            settings = "os"
            options = {"option": ["opt_host", "opt_build", "none"]}
            default_options = {"option": "none"}

            def configure(self):
                self.output.info(">> option: {}".format(self.options.option))

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    protobuf = textwrap.dedent("""
        from conans import ConanFile

        class Protobuf(ConanFile):
            name = "protobuf"
            version = "testing"

            settings = "os"  # , "arch", "compiler", "build_type"
            options = {"option": ["opt_host", "opt_build", "none"]}
            default_options = {"option": "none"}

            def build_requirements(self):
                self.build_requires("gtest/testing@user/channel", context="host")

            def configure(self):
                self.output.info(">> option: {}".format(self.options.option))

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    protoc = textwrap.dedent("""
        from conans import ConanFile

        class Protoc(ConanFile):
            name = "protoc"
            version = "testing"

            settings = "os"
            options = {"option": ["opt_host", "opt_build", "none"]}
            default_options = {"option": "none"}
            requires = "protobuf/testing@user/channel"

            def configure(self):
                self.output.info(">> option: {}".format(self.options.option))

            def build(self):
                self.output.info(">> settings.os: {}".format(self.settings.os))
    """)

    application = textwrap.dedent("""
        from conans import ConanFile

        class Application(ConanFile):
            name = "application"
            version = "testing"

            settings = "os"
            default_options = {"*:option": "opt_host"}
            default_build_options = {"*:option": "opt_build"}

            def build_requirements(self):
                self.build_requires("protoc/testing@user/channel", context="host")
                self.build_requires("protoc/testing@user/channel", context="build")

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    settings_yml = textwrap.dedent("""
        os:
            Host:
            Build:
    """)

    def setUp(self):
        super(OptionsSpecifiedInRecipes, self).setUp()
        self._cache_recipe("gtest/testing@user/channel", self.gtest)
        self._cache_recipe("protobuf/testing@user/channel", self.protobuf)
        self._cache_recipe("protoc/testing@user/channel", self.protoc)
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
        graph_info = GraphInfo(profile_build=profile_build, profile_host=profile_host,
                               options=OptionsValues(), build_options=OptionsValues(), root_ref=ref)

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
        self.assertEqual(str(application.conanfile.settings.os), profile_host.settings['os'])

        protoc_host = application.dependencies[1].dst
        self.assertEqual(protoc_host.conanfile.name, "protoc")
        self.assertEqual(protoc_host.build_context, CONTEXT_HOST)
        self.assertEqual(str(protoc_host.conanfile.settings.os), profile_host.settings['os'])
        self.assertEqual(str(protoc_host.conanfile.options.option), "opt_host")

        protobuf_host = protoc_host.dependencies[0].dst
        self.assertEqual(protobuf_host.conanfile.name, "protobuf")
        self.assertEqual(protobuf_host.build_context, CONTEXT_HOST)
        self.assertEqual(str(protobuf_host.conanfile.settings.os), profile_host.settings['os'])
        self.assertEqual(str(protobuf_host.conanfile.options.option), "opt_host")

        gtest_host = protobuf_host.dependencies[0].dst
        self.assertEqual(gtest_host.conanfile.name, "gtest")
        self.assertEqual(gtest_host.build_context, CONTEXT_HOST)
        self.assertEqual(str(gtest_host.conanfile.settings.os), profile_host.settings['os'])
        self.assertEqual(str(gtest_host.conanfile.options.option), "opt_host")

        # Check BUILD packages
        protoc_build = application.dependencies[0].dst
        self.assertEqual(protoc_build.conanfile.name, "protoc")
        self.assertEqual(protoc_build.build_context, CONTEXT_BUILD)
        self.assertEqual(str(protoc_build.conanfile.settings.os), profile_build.settings['os'])
        self.assertEqual(str(protoc_build.conanfile.options.option), "opt_build")

        protobuf_build = protoc_build.dependencies[0].dst
        self.assertEqual(protobuf_build.conanfile.name, "protobuf")
        self.assertEqual(protobuf_build.build_context, CONTEXT_BUILD)
        self.assertEqual(str(protobuf_build.conanfile.settings.os), profile_build.settings['os'])
        self.assertEqual(str(protobuf_build.conanfile.options.option), "opt_build")

        gtest_build = protobuf_build.dependencies[0].dst
        self.assertEqual(gtest_build.conanfile.name, "gtest")
        self.assertEqual(gtest_build.build_context, CONTEXT_BUILD)
        self.assertEqual(str(gtest_build.conanfile.settings.os), profile_build.settings['os'])
        self.assertEqual(str(gtest_build.conanfile.options.option), "opt_build")
