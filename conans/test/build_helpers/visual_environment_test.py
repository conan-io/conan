import unittest

from conans import tools
from conans.test.utils.conanfile import MockConanfile, MockSettings
from conans.client.build.visual_environment import VisualStudioBuildEnvironment


class VisualStudioBuildEnvironmentTest(unittest.TestCase):

    def test_visual(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compier": "Visual Studio",
                                 "compiler.runtime": "MDd"})
        conanfile = MockConanfile(settings)
        conanfile.deps_cpp_info.include_paths.append("/one/include/path")
        conanfile.deps_cpp_info.include_paths.append("/two/include/path")
        conanfile.deps_cpp_info.lib_paths.append("/one/lib/path")
        conanfile.deps_cpp_info.lib_paths.append("/two/lib/path")
        conanfile.deps_cpp_info.cflags.append("-mycflag")
        conanfile.deps_cpp_info.cflags.append("-mycflag2")
        conanfile.deps_cpp_info.cppflags.append("-mycppflag")
        conanfile.deps_cpp_info.cppflags.append("-mycppflag2")
        conanfile.deps_cpp_info.exelinkflags.append("-myexelinkflag")
        conanfile.deps_cpp_info.sharedlinkflags.append("-mysharedlinkflag")

        tool = VisualStudioBuildEnvironment(conanfile)
        self.assertEquals(tool.vars_dict, {
            "CL": ["-I/one/include/path", "-I/two/include/path",
                   '-MDd',
                   '-mycflag',
                   '-mycflag2',
                   '-Zi',
                   '-mycppflag',
                   '-mycppflag2',
                   '-myexelinkflag',
                   '-mysharedlinkflag'],
            "LIB": ["/one/lib/path", "/two/lib/path"],
        })

        # Now alter the paths before the vars_dict call
        tool.include_paths.append("/three/include/path")
        tool.lib_paths.append("/three/lib/path")

        self.assertEquals(tool.vars_dict, {
            "CL": ["-I/one/include/path",
                   "-I/two/include/path",
                   "-I/three/include/path",
                   '-MDd',
                   '-mycflag',
                   '-mycflag2',
                   '-Zi',
                   '-mycppflag',
                   '-mycppflag2',
                   '-myexelinkflag',
                   '-mysharedlinkflag'],
            "LIB": ["/one/lib/path", "/two/lib/path", "/three/lib/path"],
        })

        # Now try appending to environment
        with tools.environment_append({"CL": "-I/four/include/path -I/five/include/path",
                                       "LIB": "/four/lib/path;/five/lib/path"}):
            self.assertEquals(tool.vars_dict, {
                "CL": ["-I/one/include/path", "-I/two/include/path",
                       "-I/three/include/path",
                       '-MDd',
                       '-mycflag',
                       '-mycflag2',
                       '-Zi',
                       '-mycppflag',
                       '-mycppflag2',
                       '-myexelinkflag',
                       '-mysharedlinkflag',
                       "-I/four/include/path -I/five/include/path"],
                "LIB": ["/one/lib/path", "/two/lib/path", "/three/lib/path", "/four/lib/path;/five/lib/path"],
            })

            self.assertEquals(tool.vars, {
                "CL": '-I"/one/include/path" -I"/two/include/path" -I"/three/include/path" -MDd '
                      '-mycflag -mycflag2 -Zi '
                      '-mycppflag -mycppflag2 -myexelinkflag -mysharedlinkflag '
                      '-I/four/include/path -I/five/include/path',
                "LIB": "/one/lib/path;/two/lib/path;/three/lib/path;/four/lib/path;/five/lib/path",
            })
