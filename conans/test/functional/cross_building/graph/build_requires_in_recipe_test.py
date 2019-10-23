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


class BuildRequiresInRecipeExample(GraphManagerTest):
    """ There is an application with a requirement 'lib', both of them build_requires
        a tool called 'breq' (build_machine) and this tool requires a 'breq_lib'.

        All these requirements are declared in the profiles
    """

    breq_lib = textwrap.dedent("""
        from conans import ConanFile

        class BuildRequiresLibrary(ConanFile):
            name = "breq_lib"
            version = "testing"

            settings = "os"

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    breq = textwrap.dedent("""
        from conans import ConanFile

        class BuildRequires(ConanFile):
            name = "breq"
            version = "testing"

            settings = "os"
            requires = "breq_lib/testing@user/channel"

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    lib = textwrap.dedent("""
        from conans import ConanFile

        class Library(ConanFile):
            name = "protobuf"
            version = "testing"

            settings = "os"  # , "arch", "compiler", "build_type"

            def build_requirements(self):
                self.build_requires("breq/testing@user/channel")

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    application = textwrap.dedent("""
        from conans import ConanFile

        class Application(ConanFile):
            name = "application"
            version = "testing"

            settings = "os"
            requires = "lib/testing@user/channel"

            def build_requirements(self):
                self.build_requires("breq/testing@user/channel")

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    settings_yml = textwrap.dedent("""
        os:
            Host:
            Build:
    """)

    breq_lib_ref = ConanFileReference.loads("breq_lib/testing@user/channel")
    breq_ref = ConanFileReference.loads("breq/testing@user/channel")
    lib_ref = ConanFileReference.loads("lib/testing@user/channel")
    application_ref = ConanFileReference.loads("application/testing@user/channel")

    def setUp(self):
        super(BuildRequiresInRecipeExample, self).setUp()
        self._cache_recipe(self.breq_lib_ref, self.breq_lib)
        self._cache_recipe(self.breq_ref, self.breq)
        self._cache_recipe(self.lib_ref, self.lib)
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
        graph_info = GraphInfo(profile_build=profile_build, profile=profile_host,
                               options=options, root_ref=ref)

        recorder = ActionRecorder()
        app = self._get_app()
        deps_graph = app.graph_manager.load_graph(path, create_reference=None, graph_info=graph_info,
                                                  build_mode=[], check_updates=False, update=False,
                                                  remotes=Remotes(), recorder=recorder)
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
        self.assertEqual(application.context, CONTEXT_HOST)
        self.assertEqual(application.conanfile.settings.os, profile_host.settings['os'])

        lib_host = application.dependencies[0].dst
        self.assertEqual(lib_host.conanfile.name, "lib")
        self.assertEqual(lib_host.context, CONTEXT_HOST)
        self.assertEqual(lib_host.conanfile.settings.os, profile_host.settings['os'])

        # Check BUILD packages
        breq_application_build = application.dependencies[1].dst
        self.assertEqual(breq_application_build.conanfile.name, "breq")
        self.assertEqual(breq_application_build.context, CONTEXT_BUILD)
        self.assertEqual(str(breq_application_build.conanfile.settings.os),
                         profile_build.settings['os'])

        breq_lib_build = lib_host.dependencies[0].dst
        self.assertNotEqual(breq_application_build, breq_lib_build)
        self.assertEqual(breq_lib_build.conanfile.name, "breq")
        self.assertEqual(breq_lib_build.context, CONTEXT_BUILD)
        self.assertEqual(str(breq_lib_build.conanfile.settings.os), profile_build.settings['os'])

        breq_lib_build = breq_application_build.dependencies[0].dst
        self.assertEqual(breq_lib_build.conanfile.name, "breq_lib")
        self.assertEqual(breq_lib_build.context, CONTEXT_BUILD)
        self.assertEqual(str(breq_lib_build.conanfile.settings.os), profile_build.settings['os'])
