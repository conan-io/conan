import textwrap

from conans.client.graph.graph import CONTEXT_BUILD, CONTEXT_HOST
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.test.functional.cross_building.graph._base_test_case import CrossBuildingBaseTestCase


class BuildRequireOfBuildRequire(CrossBuildingBaseTestCase):
    """ There is an application that build_requires three different tools:
         * cmake (build)
         * gtest (host), that build_requires 'cmake'
         * protoc (build), that build_requires 'cmake' too
    """

    cmake = textwrap.dedent("""
        from conans import ConanFile

        class BuildRequiresLibrary(ConanFile):
            name = "cmake"
            version = "testing"

            settings = "os"

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
                
            def package_info(self):
                cmake_str = "cmake-host" if self.settings.os == "Host" else "cmake-build"

                self.cpp_info.includedirs = [cmake_str, ]
                self.cpp_info.libdirs = [cmake_str, ]
                self.cpp_info.bindirs = [cmake_str, ]
                
                self.env_info.PATH.append(cmake_str)
                self.env_info.OTHERVAR = cmake_str
    """)

    gtest = textwrap.dedent("""
        from conans import ConanFile

        class BuildRequires(ConanFile):
            name = "gtest"
            version = "testing"

            settings = "os"

            def build_requirements(self):
                self.build_requires("cmake/testing@user/channel")

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))

            def package_info(self):
                gtest_str = "gtest-host" if self.settings.os == "Host" else "gtest-build"

                self.cpp_info.includedirs = [gtest_str, ]
                self.cpp_info.libdirs = [gtest_str, ]
                self.cpp_info.bindirs = [gtest_str, ]

                self.env_info.PATH.append(gtest_str)
                self.env_info.OTHERVAR = gtest_str
    """)

    protoc = textwrap.dedent("""
        from conans import ConanFile

        class BuildRequires(ConanFile):
            name = "protoc"
            version = "testing"

            settings = "os"

            def build_requirements(self):
                self.build_requires("cmake/testing@user/channel")

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

        class Application(ConanFile):
            name = "app"
            version = "testing"

            settings = "os"

            def build_requirements(self):
                self.build_requires("cmake/testing@user/channel")
                self.build_requires("gtest/testing@user/channel", force_host_context=True)
                self.build_requires("protoc/testing@user/channel")

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    cmake_ref = ConanFileReference.loads("cmake/testing@user/channel")
    gtest_ref = ConanFileReference.loads("gtest/testing@user/channel")
    protoc_ref = ConanFileReference.loads("protoc/testing@user/channel")

    def setUp(self):
        super(BuildRequireOfBuildRequire, self).setUp()
        self._cache_recipe(self.cmake_ref, self.cmake)
        self._cache_recipe(self.gtest_ref, self.gtest)
        self._cache_recipe(self.protoc_ref, self.protoc)
        self._cache_recipe(self.app_ref, self.application)

    def test_crossbuilding(self):
        profile_host = Profile()
        profile_host.settings["os"] = "Host"
        profile_host.process_settings(self.cache)

        profile_build = Profile()
        profile_build.settings["os"] = "Build"
        profile_build.process_settings(self.cache)

        deps_graph = self._build_graph(profile_host=profile_host, profile_build=profile_build,
                                       install=True)

        # Check HOST packages
        #   - Application
        application = deps_graph.root.dependencies[0].dst
        self.assertEqual(len(application.dependencies), 3)
        self.assertEqual(application.conanfile.name, "app")
        self.assertEqual(application.context, CONTEXT_HOST)
        self.assertEqual(application.conanfile.settings.os, profile_host.settings['os'])

        #   - Application::deps_cpp_info:
        gtest_cpp_info = application.conanfile.deps_cpp_info["gtest"]
        self.assertEqual(gtest_cpp_info.includedirs, ['gtest-host'])
        self.assertEqual(gtest_cpp_info.libdirs, ['gtest-host'])
        self.assertEqual(gtest_cpp_info.bindirs, ['gtest-host'])

        with self.assertRaises(KeyError):
            _ = application.conanfile.deps_cpp_info["cmake"]

        with self.assertRaises(KeyError):
            _ = application.conanfile.deps_cpp_info["protoc"]

        #   - Application::deps_env_info:
        cmake_env_info = application.conanfile.deps_env_info["cmake"]
        self.assertEqual(cmake_env_info.PATH, ['cmake-build'])
        self.assertEqual(cmake_env_info.OTHERVAR, 'cmake-build')

        protoc_env_info = application.conanfile.deps_env_info["protoc"]
        self.assertEqual(protoc_env_info.PATH, ['protoc-build'])
        self.assertEqual(protoc_env_info.OTHERVAR, 'protoc-build')

        with self.assertRaises(KeyError):
            _ = application.conanfile.deps_env_info["gtest"]

        #   - GTest
        gtest_host = application.dependencies[1].dst
        self.assertEqual(gtest_host.conanfile.name, "gtest")
        self.assertEqual(gtest_host.context, CONTEXT_HOST)
        self.assertEqual(gtest_host.conanfile.settings.os, profile_host.settings['os'])

        #   - GTest::deps_cpp_info:
        with self.assertRaises(KeyError):
            _ = gtest_host.conanfile.deps_cpp_info["cmake"]

        #   - GTest::deps_env_info:
        cmake_env_info = gtest_host.conanfile.deps_env_info["cmake"]
        self.assertEqual(cmake_env_info.PATH, ['cmake-build'])
        self.assertEqual(cmake_env_info.OTHERVAR, 'cmake-build')

        # Check BUILD packages
        #   - CMake
        cmake_build = application.dependencies[0].dst
        self.assertEqual(cmake_build.conanfile.name, "cmake")
        self.assertEqual(cmake_build.context, CONTEXT_BUILD)
        self.assertEqual(str(cmake_build.conanfile.settings.os), profile_build.settings['os'])

        #   - Protoc
        protoc_build = application.dependencies[2].dst
        self.assertEqual(protoc_build.conanfile.name, "protoc")
        self.assertEqual(protoc_build.context, CONTEXT_BUILD)
        self.assertEqual(str(protoc_build.conanfile.settings.os), profile_build.settings['os'])

        #   - Protoc::deps_cpp_info:
        with self.assertRaises(KeyError):
            _ = protoc_build.conanfile.deps_cpp_info["cmake"]

        #   - Protoc::deps_env_info:
        cmake_env_info = protoc_build.conanfile.deps_env_info["cmake"]
        self.assertEqual(cmake_env_info.PATH, ['cmake-build'])
        self.assertEqual(cmake_env_info.OTHERVAR, 'cmake-build')

        #   - CMake <- Protoc
        cmake_protoc_build = protoc_build.dependencies[0].dst
        self.assertNotEqual(cmake_build, cmake_protoc_build)
        self.assertEqual(cmake_protoc_build.conanfile.name, "cmake")
        self.assertEqual(cmake_protoc_build.context, CONTEXT_BUILD)
        self.assertEqual(str(cmake_protoc_build.conanfile.settings.os), profile_build.settings['os'])

        #   - CMake <- GTest
        cmake_gtest_build = gtest_host.dependencies[0].dst
        self.assertNotEqual(cmake_build, cmake_gtest_build)
        self.assertEqual(cmake_gtest_build.conanfile.name, "cmake")
        self.assertEqual(cmake_gtest_build.context, CONTEXT_BUILD)
        self.assertEqual(str(cmake_gtest_build.conanfile.settings.os), profile_build.settings['os'])
