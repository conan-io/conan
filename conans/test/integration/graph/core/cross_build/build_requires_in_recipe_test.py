import textwrap

from conans.client.graph.graph import CONTEXT_BUILD, CONTEXT_HOST
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.test.integration.graph.core.cross_build._base_test_case import CrossBuildingBaseTestCase


class BuildRequiresInRecipeExample(CrossBuildingBaseTestCase):
    """ There is an application with a requirement 'lib', both of them build_requires
        a tool called 'breq' (build_machine) and this tool requires a 'breq_lib'.

        All these requirements are declared in the recipes
    """
    application = textwrap.dedent("""
        from conans import ConanFile

        class Application(ConanFile):
            name = "app"
            version = "testing"

            settings = "os"
            requires = "lib/testing@user/channel"

            def build_requirements(self):
                self.build_requires("breq/testing@user/channel")

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    breq = CrossBuildingBaseTestCase.library_tpl.render(name="breq",
                                                        requires=["breq_lib/testing@user/channel", ])
    breq_lib = CrossBuildingBaseTestCase.library_tpl.render(name="breq_lib")
    lib = CrossBuildingBaseTestCase.library_tpl.render(
        name="lib", build_requires=[("breq/testing@user/channel", False), ])

    breq_lib_ref = ConanFileReference.loads("breq_lib/testing@user/channel")
    breq_ref = ConanFileReference.loads("breq/testing@user/channel")
    lib_ref = ConanFileReference.loads("lib/testing@user/channel")

    def setUp(self):
        super(BuildRequiresInRecipeExample, self).setUp()
        self._cache_recipe(self.breq_lib_ref, self.breq_lib)
        self._cache_recipe(self.breq_ref, self.breq)
        self._cache_recipe(self.lib_ref, self.lib)
        self._cache_recipe(self.app_ref, self.application)

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
        self.assertEqual(application.conanfile.name, "app")
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
        self.assertEqual(str(breq_application_build.conanfile.settings.os), profile_build.settings['os'])

        breq_lib_build = lib_host.dependencies[0].dst
        self.assertNotEqual(breq_application_build, breq_lib_build)
        self.assertEqual(breq_lib_build.conanfile.name, "breq")
        self.assertEqual(breq_lib_build.context, CONTEXT_BUILD)
        self.assertEqual(str(breq_lib_build.conanfile.settings.os), profile_build.settings['os'])

        breq_lib_build = breq_application_build.dependencies[0].dst
        self.assertEqual(breq_lib_build.conanfile.name, "breq_lib")
        self.assertEqual(breq_lib_build.context, CONTEXT_BUILD)
        self.assertEqual(str(breq_lib_build.conanfile.settings.os), profile_build.settings['os'])
