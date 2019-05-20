# coding=utf-8

import os
import textwrap

from conans.client.cache.remote_registry import Remotes
from conans.client.recorder.action_recorder import ActionRecorder
from conans.model.graph_info import GraphInfo
from conans.model.options import OptionsValues
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.test.functional.graph.graph_manager_base import GraphManagerTest
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class NoWayBackToHost(GraphManagerTest):
    """ There is an application that build_requires (build) a tool and it is trying to
        build_require another tool from the "host" context. As there are
        no more context changes available once we entered the 'build' context, then there is no
        way back to the original host context because build=host
    """

    host_tool = textwrap.dedent("""
        from conans import ConanFile

        class HostTool(ConanFile):
            name = "host_tool"
            version = "testing"

            settings = "os"

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    build_tool = textwrap.dedent("""
        from conans import ConanFile

        class BuildTool(ConanFile):
            name = "build_tool"
            version = "testing"

            settings = "os"
            
            def build_requirements(self):
                # From the perspective of this package, the "host" context is the same one
                #  as the one where `build_tool` is being built.
                self.build_requires("host_tool/testing@user/channel", context="host") 

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
                self.build_requires("build_tool/testing@user/channel")

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    settings_yml = textwrap.dedent("""
        os:
            Host:
            Build:
    """)

    def setUp(self):
        super(NoWayBackToHost, self).setUp()
        self._cache_recipe("host_tool/testing@user/channel", self.host_tool)
        self._cache_recipe("build_tool/testing@user/channel", self.build_tool)
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
        self.assertEqual(len(application.dependencies), 1)
        self.assertEqual(application.conanfile.name, "application")
        self.assertEqual(application.build_context, "host")
        self.assertEqual(application.conanfile.settings.os, profile_host.settings['os'])

        # Check BUILD package
        build_tool = application.dependencies[0].dst
        self.assertEqual(build_tool.conanfile.name, "build_tool")
        self.assertEqual(build_tool.build_context, "build")
        self.assertEqual(build_tool.conanfile.settings.os, profile_build.settings['os'])

        # There is no way back to host profile from build one (host=build)
        host_tool = build_tool.dependencies[0].dst
        self.assertEqual(host_tool.conanfile.name, "host_tool")
        self.assertEqual(host_tool.build_context, "build")
        self.assertEqual(str(host_tool.conanfile.settings.os), profile_host.settings['os'])
