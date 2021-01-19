import unittest

from conans.client import tools
from conans.client.build.visual_environment import VisualStudioBuildEnvironment
from conans.test.utils.mocks import MockSettings, MockConanfile
from conans.test.utils.tools import TestClient


class VisualStudioBuildEnvironmentTest(unittest.TestCase):

    def test_visual(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.runtime": "MDd"})
        conanfile = MockConanfile(settings)
        conanfile.deps_cpp_info.include_paths.append("/one/include/path")
        conanfile.deps_cpp_info.include_paths.append("/two/include/path")
        conanfile.deps_cpp_info.lib_paths.append("/one/lib/path")
        conanfile.deps_cpp_info.lib_paths.append("/two/lib/path")
        conanfile.deps_cpp_info.cflags.append("-mycflag")
        conanfile.deps_cpp_info.cflags.append("-mycflag2")
        conanfile.deps_cpp_info.cxxflags.append("-mycxxflag")
        conanfile.deps_cpp_info.cxxflags.append("-mycxxflag2")
        conanfile.deps_cpp_info.exelinkflags.append("-myexelinkflag")
        conanfile.deps_cpp_info.sharedlinkflags.append("-mysharedlinkflag")
        conanfile.deps_cpp_info.libs.extend(['gdi32', 'user32.lib'])

        tool = VisualStudioBuildEnvironment(conanfile)
        self.assertEqual(tool.vars_dict, {
            "CL": ["-I/one/include/path", "-I/two/include/path",
                   '-MDd',
                   '-mycflag',
                   '-mycflag2',
                   '-Zi',
                   '-Ob0',
                   '-Od',
                   '-mycxxflag',
                   '-mycxxflag2'],
            "LIB": ["/one/lib/path", "/two/lib/path"],
            "UseEnv": "True",
            "_LINK_": ['-myexelinkflag', '-mysharedlinkflag', 'gdi32.lib', 'user32.lib']
        })
        tool.parallel = True
        self.assertEqual(tool.vars_dict, {
            "CL": ["-I/one/include/path", "-I/two/include/path",
                   '-MDd',
                   '-mycflag',
                   '-mycflag2',
                   '-Zi',
                   '-Ob0',
                   '-Od',
                   '-mycxxflag',
                   '-mycxxflag2',
                   '/MP%s' % tools.cpu_count(output=conanfile.output)],
            "LIB": ["/one/lib/path", "/two/lib/path"],
            "UseEnv": "True",
            "_LINK_": ['-myexelinkflag', '-mysharedlinkflag', 'gdi32.lib', 'user32.lib']
        })
        tool.parallel = False

        # Now alter the paths before the vars_dict call
        tool.include_paths.append("/three/include/path")
        tool.lib_paths.append("/three/lib/path")

        self.assertEqual(tool.vars_dict, {
            "CL": ["-I/one/include/path",
                   "-I/two/include/path",
                   "-I/three/include/path",
                   '-MDd',
                   '-mycflag',
                   '-mycflag2',
                   '-Zi',
                   '-Ob0',
                   '-Od',
                   '-mycxxflag',
                   '-mycxxflag2'],
            "LIB": ["/one/lib/path", "/two/lib/path", "/three/lib/path"],
            "UseEnv": "True",
            "_LINK_": ['-myexelinkflag', '-mysharedlinkflag', 'gdi32.lib', 'user32.lib']
        })

        # Now try appending to environment
        with tools.environment_append({"CL": "-I/four/include/path -I/five/include/path",
                                       "LIB": "/four/lib/path;/five/lib/path"}):
            self.assertEqual(tool.vars_dict, {
                "CL": ["-I/one/include/path", "-I/two/include/path",
                       "-I/three/include/path",
                       '-MDd',
                       '-mycflag',
                       '-mycflag2',
                       '-Zi',
                       '-Ob0',
                       '-Od',
                       '-mycxxflag',
                       '-mycxxflag2',
                       "-I/four/include/path -I/five/include/path"],
                "LIB": ["/one/lib/path", "/two/lib/path", "/three/lib/path",
                        "/four/lib/path;/five/lib/path"],
                "UseEnv": "True",
                "_LINK_": ['-myexelinkflag', '-mysharedlinkflag', 'gdi32.lib', 'user32.lib']
            })

            self.assertEqual(tool.vars, {
                "CL": '-I"/one/include/path" -I"/two/include/path" -I"/three/include/path" -MDd '
                      '-mycflag -mycflag2 -Zi -Ob0 -Od '
                      '-mycxxflag -mycxxflag2 '
                      '-I/four/include/path -I/five/include/path',
                "LIB": "/one/lib/path;/two/lib/path;/three/lib/path;/four/lib/path;/five/lib/path",
                "UseEnv": "True",
                "_LINK_": "-myexelinkflag -mysharedlinkflag gdi32.lib user32.lib"
            })

    def test_build_type_toolset(self):
        profile = """
[settings]
os=Windows
compiler=Visual Studio
compiler.version=15
build_type=Release
"""
        profile_toolset = """
[settings]
os=Windows
compiler=Visual Studio
compiler.version=15
compiler.toolset=v141
build_type=Release
"""
        profile_toolset_clang = """
[settings]
os=Windows
compiler=Visual Studio
compiler.version=15
build_type=Release
compiler.toolset=v141_clang_c2
"""
        conanfile = """
from conans import ConanFile, VisualStudioBuildEnvironment

class TestConan(ConanFile):
    name = "testlib"
    version = "1.0"
    settings = "compiler", "build_type", "os"

    def build(self):
        env_build = VisualStudioBuildEnvironment(self)
        self.output.info(env_build.flags)
        """
        client = TestClient()
        client.save({"profile": profile,
                     "profile_toolset": profile_toolset,
                     "profile_toolset_clang": profile_toolset_clang,
                     "conanfile.py": conanfile})

        result = {"Debug": "['-Zi', '-Ob0', '-Od']",
                  "Release": "['-DNDEBUG', '-O2', '-Ob2']",
                  "RelWithDebInfo": "['-DNDEBUG', '-Zi', '-O2', '-Ob1']",
                  "MinSizeRel": "['-DNDEBUG', '-O1', '-Ob1']"}
        result_toolset_clang = {"Debug": "['-gline-tables-only', '-fno-inline', '-O0']",
                                "Release": "['-DNDEBUG', '-O2']",
                                "RelWithDebInfo": "['-DNDEBUG', '-gline-tables-only', '-O2', '-fno-inline']",
                                "MinSizeRel": "['-DNDEBUG']"}

        for build_type in ["Debug", "Release", "RelWithDebInfo", "MinSizeRel"]:
            client.run("create . danimtb/testing -pr=profile -s build_type=%s" % build_type)
            self.assertIn(result[build_type], client.out)
            client.run("create . danimtb/testing -pr=profile_toolset -s build_type=%s" % build_type)
            self.assertIn(result[build_type], client.out)
            client.run("create . danimtb/testing -pr=profile_toolset_clang -s build_type=%s" %
                       build_type)
            self.assertIn(result_toolset_clang[build_type], client.out)
