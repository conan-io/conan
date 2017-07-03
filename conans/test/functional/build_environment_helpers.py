import unittest

from conans import tools
from conans.client.configure_build_environment import VisualStudioBuildEnvironment
from conans.test.utils.conanfile import MockConanfile, MockSettings


class BuildEnvironmentHelpers(unittest.TestCase):

    def test_visual(self):
        settings = MockSettings({})
        conanfile = MockConanfile(settings)
        conanfile.deps_cpp_info.include_paths.append("/one/include/path")
        conanfile.deps_cpp_info.include_paths.append("/two/include/path")
        conanfile.deps_cpp_info.lib_paths.append("/one/lib/path")
        conanfile.deps_cpp_info.lib_paths.append("/two/lib/path")
        tool = VisualStudioBuildEnvironment(conanfile)
        self.assertEquals(tool.vars_dict, {
            "CL": ["/I/one/include/path", "/I/two/include/path"],
            "LIB": ["/one/lib/path", "/two/lib/path"],
        })

        # Now alter the paths before the vars_dict call
        tool.include_paths.append("/three/include/path")
        tool.lib_paths.append("/three/lib/path")

        self.assertEquals(tool.vars_dict, {
            "CL": ["/I/one/include/path", "/I/two/include/path", "/I/three/include/path"],
            "LIB": ["/one/lib/path", "/two/lib/path", "/three/lib/path"],
        })

        # Now try appending to environment
        with tools.environment_append({"CL": "/I/four/include/path /I/five/include/path",
                                       "LIB": "/four/lib/path;/five/lib/path"}):
            self.assertEquals(tool.vars_dict, {
                "CL": ["/I/one/include/path", "/I/two/include/path",
                       "/I/three/include/path", "/I/four/include/path /I/five/include/path"],
                "LIB": ["/one/lib/path", "/two/lib/path", "/three/lib/path", "/four/lib/path;/five/lib/path"],
            })

            self.assertEquals(tool.vars, {
                "CL": '/I"/one/include/path" /I"/two/include/path" '
                      '/I"/three/include/path" /I/four/include/path /I/five/include/path',
                "LIB": "/one/lib/path;/two/lib/path;/three/lib/path;/four/lib/path;/five/lib/path",
            })
æ