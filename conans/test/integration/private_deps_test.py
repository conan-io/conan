import os
import unittest

from conans.test.utils.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.paths import CONANINFO, BUILD_INFO_CMAKE
from conans.util.files import load
from conans.model.info import ConanInfo
from nose.plugins.attrib import attr


class PrivateBinariesTest(unittest.TestCase):
    def test_transitive_private(self):
        # https://github.com/conan-io/conan/issues/3523
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass
    def package_info(self):
        self.cpp_info.libs = [self.name]
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . PkgC/0.1@user/channel")
        client.save({"conanfile.py": conanfile.replace("pass", "requires='PkgC/0.1@user/channel'")})
        client.run("create . PkgB/0.1@user/channel")
        client.save({"conanfile.py":
                     conanfile.replace("pass", "requires=('PkgB/0.1@user/channel', 'private'), "
                                               "'PkgC/0.1@user/channel'")})
        client.run("create . PkgA/0.1@user/channel")
        client.save({"conanfile.py": conanfile.replace("pass", "requires='PkgA/0.1@user/channel'")})
        client.run("install . -g=cmake")
        self.assertIn("PkgC/0.1@user/channel:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache",
                      client.out)
        conanbuildinfo = load(os.path.join(client.current_folder, "conanbuildinfo.txt"))
        self.assertIn("[libs];PkgA;PkgC", ";".join(conanbuildinfo.splitlines()))
        self.assertIn("PkgC/0.1/user/channel/package", conanbuildinfo)
        self.assertIn("[includedirs_PkgC]", conanbuildinfo)
        conanbuildinfo = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        self.assertIn("set(CONAN_LIBS PkgA PkgC ${CONAN_LIBS})", conanbuildinfo)
        client.run("info . --graph=file.html")
        html = load(os.path.join(client.current_folder, "file.html"))
        self.assertEqual(2, html.count("label: 'PkgC/0.1', shape: 'box'"))

    def test_private_regression_skip(self):
        # https://github.com/conan-io/conan/issues/3166
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@user/channel")
        client.save({"conanfile.py": conanfile.replace("pass", "requires=('Pkg/0.1@user/channel', 'private'),")})
        client.run("create . Pkg2/0.1@user/channel")
        client.save({"conanfile.py": conanfile.replace("pass", "requires=('Pkg2/0.1@user/channel', 'private'),")})
        client.run("create . Pkg3/0.1@user/channel")
        client.save({"conanfile.py": conanfile.replace("pass", "requires=('Pkg3/0.1@user/channel', 'private'),")})
        client.run("create . Pkg4/0.1@user/channel")
        client.run("info Pkg4/0.1@user/channel")
        self.assertEqual(3, str(client.out).count("Binary: Skip"))

    def test_private_skip(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    def package_info(self):
        self.cpp_info.libs = ["zlib"]
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . zlib/1.2.11@conan/stable")
        client.save({"conanfile.py": conanfile.replace("zlib", "bzip2")})
        client.run("create . bzip2/1.0.6@conan/stable")
        conanfile = """from conans import ConanFile
class MyPackage(ConanFile):
    requires = ('zlib/1.2.11@conan/stable', ('bzip2/1.0.6@conan/stable', 'private'),)
    def package_info(self):
        self.cpp_info.libs = ["mypackage"]
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . MyPackage/1.0@testing/testing")
        client.run("remove bzip2/1.0.6@conan/stable -p -f")
        conanfile = """from conans import ConanFile
class V3D(ConanFile):
    requires = "zlib/1.2.11@conan/stable", "MyPackage/1.0@testing/testing"
"""
        client.save({"conanfile.py": conanfile})
        client.run("install . -g=cmake")
        self.assertIn("bzip2/1.0.6@conan/stable:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Skip",
                      client.out)
        self.assertIn("zlib/1.2.11@conan/stable:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache",
                      client.out)
        conanbuildinfo = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        # The order is dictated by public MyPackage -> zlib dependency
        self.assertIn("set(CONAN_LIBS mypackage zlib ${CONAN_LIBS})", conanbuildinfo)
        self.assertNotIn("bzip2", conanbuildinfo)

    def test_multiple_private_skip(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    def package_info(self):
        self.cpp_info.libs = ["zlib"]
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . zlib/1.2.11@conan/stable")
        client.save({"conanfile.py": conanfile.replace("zlib", "bzip2")})
        client.run("create . bzip2/1.0.6@conan/stable")
        conanfile = """from conans import ConanFile
class MyPackage(ConanFile):
    requires = ('zlib/1.2.11@conan/stable', 'private'), ('bzip2/1.0.6@conan/stable', 'private')
    def package_info(self):
        self.cpp_info.libs = ["mypackage"]
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . MyPackage/1.0@testing/testing")
        client.run("remove bzip2/1.0.6@conan/stable -p -f")
        client.run("remove zlib* -p -f")
        conanfile = """from conans import ConanFile
class V3D(ConanFile):
    requires = "zlib/1.2.11@conan/stable", "MyPackage/1.0@testing/testing"
"""
        client.save({"conanfile.py": conanfile})
        error = client.run("install . -g=cmake", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Missing prebuilt package for 'zlib/1.2.11@conan/stable'",
                      client.out)
        client.run("install zlib/1.2.11@conan/stable --build=missing")
        client.run("install . -g=cmake")
        self.assertIn("bzip2/1.0.6@conan/stable:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Skip",
                      client.out)
        self.assertIn("zlib/1.2.11@conan/stable:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache",
                      client.out)
        conanbuildinfo = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        # The order is dictated by V3D declaration order, as other are privates
        self.assertIn("set(CONAN_LIBS zlib mypackage ${CONAN_LIBS})", conanbuildinfo)
        self.assertNotIn("bzip2", conanbuildinfo)

    def test_own_private_skip(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    def package_info(self):
        self.cpp_info.libs = ["zlib"]
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . zlib/1.2.11@conan/stable")
        client.save({"conanfile.py": conanfile.replace("zlib", "bzip2")})
        client.run("create . bzip2/1.0.6@conan/stable")
        conanfile = """from conans import ConanFile
class MyPackage(ConanFile):
    requires = 'zlib/1.2.11@conan/stable', ('bzip2/1.0.6@conan/stable', 'private')
    def package_info(self):
        self.cpp_info.libs = ["mypackage"]
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . MyPackage/1.0@testing/testing")
        client.run("remove bzip2/1.0.6@conan/stable -p -f")
        conanfile = """from conans import ConanFile
class V3D(ConanFile):
    requires = ("zlib/1.2.11@conan/stable", "private"), "MyPackage/1.0@testing/testing"
"""
        client.save({"conanfile.py": conanfile})
        client.run("install . -g=cmake")
        self.assertIn("bzip2/1.0.6@conan/stable:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Skip",
                      client.out)
        self.assertIn("zlib/1.2.11@conan/stable:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache",
                      client.out)
        conanbuildinfo = load(os.path.join(client.current_folder, "conanbuildinfo.cmake"))
        # The order is dictated by public mypackage -> zlib
        self.assertIn("set(CONAN_LIBS mypackage zlib ${CONAN_LIBS})", conanbuildinfo)
        self.assertNotIn("bzip2", conanbuildinfo)


@attr("slow")
class PrivateDepsTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

    def _export_upload(self, name=0, version=None, deps=None, msg=None, static=True, build=True,
                       upload=True):
        dll_export = self.client.default_compiler_visual_studio and not static
        files = cpp_hello_conan_files(name, version, deps, msg=msg, static=static,
                                      private_includes=True, dll_export=dll_export, build=build,
                                      cmake_targets=False)
        conan_ref = ConanFileReference(name, version, "lasote", "stable")
        self.client.save(files, clean_first=True)
        self.client.run("export . lasote/stable")
        if upload:
            self.client.run("upload %s" % str(conan_ref))

    def _export(self, name=0, version=None, deps=None):
        files = cpp_hello_conan_files(name, version, deps,
                                      private_includes=True, build=False,
                                      cmake_targets=True)
        self.client.save(files, clean_first=True)
        self.client.run("export . lasote/stable")

    def modern_cmake_test(self):
        self._export("glew", "0.1")
        self._export("glm", "0.1")
        self._export("gf", "0.1", deps=[("glm/0.1@lasote/stable", "private"),
                                        "glew/0.1@lasote/stable"])

        self._export("ImGuiTest", "0.1", deps=["glm/0.1@lasote/stable",
                                               "gf/0.1@lasote/stable"])

        # Consuming project
        self._export("Project", "0.1", deps=["ImGuiTest/0.1@lasote/stable"])

        # Build packages for both recipes
        self.client.run('install . --build=missing')
        conanbuildinfo_cmake = load(os.path.join(self.client.current_folder,
                                                 "conanbuildinfo.cmake"))
        conanbuildinfo_cmake = " ".join(conanbuildinfo_cmake.splitlines())
        self.assertIn("CONAN_PKG::gf PROPERTY INTERFACE_LINK_LIBRARIES "
                      "${CONAN_PACKAGE_TARGETS_GF}", conanbuildinfo_cmake)
        self.assertIn("CONAN_PKG::ImGuiTest PROPERTY INTERFACE_LINK_LIBRARIES "
                      "${CONAN_PACKAGE_TARGETS_IMGUITEST}", conanbuildinfo_cmake)

    def consumer_force_build_test(self):
        """If a conanfile requires another private conanfile, but in the install is forced
        the build, the private node has to be downloaded and built"""
        self._export_upload("Hello0", "0.1", build=False, upload=False)
        self._export_upload("Hello1", "0.1", deps=[("Hello0/0.1@lasote/stable", "private")],
                            build=False, upload=False)

        # Build packages for both recipes
        self.client.run('install Hello1/0.1@lasote/stable --build missing')

        # Upload them to remote
        self.client.run("upload Hello0/0.1@lasote/stable --all")
        self.client.run("upload Hello1/0.1@lasote/stable --all")

        # Remove local recipes and packages
        self.client.run('remove Hello* -f')

        # Install them without force build, private is not retrieved
        self.client.run('install Hello1/0.1@lasote/stable --build missing')
        # FIXME: recipe should not be retrieved either
        # self.assertNotIn("Hello0/0.1@lasote/stable", self.client.user_io.out)
        self.assertNotIn("Hello0/0.1@lasote/stable: Package installed", self.client.user_io.out)

        # Remove local recipes and packages
        self.client.run('remove Hello* -f')

        # Install them without force build, private is not retrieved
        self.client.run('install Hello1/0.1@lasote/stable ')
        self.assertNotIn("Hello0/0.1@lasote/stable: Package installed", self.client.user_io.out)

        # Remove local recipes and packages
        self.client.run('remove Hello* -f')

        # Install them without forcing build
        self.client.run('install Hello1/0.1@lasote/stable --build Hello1')
        self.assertIn("Hello0/0.1@lasote/stable: Package installed", self.client.user_io.out)
        self.assertIn("Hello1/0.1@lasote/stable: Building your package", self.client.user_io.out)

    def consumer_private_test(self):
        self._export_upload("Hello0", "0.1", build=False, upload=False)
        self._export_upload("Hello1", "0.1", deps=["Hello0/0.1@lasote/stable"],
                            build=False, upload=False)
        self._export_upload("Hello2", "0.1", deps=[("Hello1/0.1@lasote/stable", "private")],
                            build=False, upload=False)
        self._export_upload("Hello3", "0.1", deps=[("Hello2/0.1@lasote/stable"),
                                                   ],
                            build=False, upload=False)

        self.client.run('install . --build missing')
        self.assertIn("Hello0/0.1@lasote/stable: Generating the package", self.client.user_io.out)
        self.assertIn("Hello1/0.1@lasote/stable: Generating the package", self.client.user_io.out)
        self.assertIn("Hello2/0.1@lasote/stable: Generating the package", self.client.user_io.out)

        self.client.run("remove Hello0* -p -f ")
        self.client.run("remove Hello1* -p -f")
        self.client.run("search Hello0/0.1@lasote/stable")
        self.assertIn("There are no packages for reference 'Hello0/0.1@lasote/stable', but package recipe found.",
                      self.client.user_io.out)
        self.client.run("search Hello1/0.1@lasote/stable")
        self.assertIn("There are no packages for reference 'Hello1/0.1@lasote/stable', but package recipe found.",
                      self.client.user_io.out)

        self.client.run('install . --build missing')
        self.assertNotIn("Hello0/0.1@lasote/stable: Generating the package",
                         self.client.user_io.out)
        self.assertNotIn("Hello1/0.1@lasote/stable: Generating the package",
                         self.client.user_io.out)

    def reuse_test(self):
        self._export_upload("Hello0", "0.1")
        self._export_upload("Hello1", "0.1", deps=[("Hello0/0.1@lasote/stable", "private")],
                            static=False)

        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        files3 = cpp_hello_conan_files("Hello3", "0.1", ["Hello1/0.1@lasote/stable"])
        client.save(files3)

        client.run('install . --build missing')
        client.run('build .')

        # assert Hello3 only depends on Hello2, and Hello1
        build_info_cmake = load(os.path.join(client.current_folder, BUILD_INFO_CMAKE))
        # Ensure it does not depend on Hello0 to build, as private in dlls
        self.assertNotIn("Hello0", repr(build_info_cmake))

        command = os.sep.join([".", "bin", "say_hello"])
        client.runner(command, cwd=client.current_folder)
        self.assertEqual(['Hello Hello3', 'Hello Hello1', 'Hello Hello0'],
                         str(client.user_io.out).splitlines()[-3:])

        conan_info = ConanInfo.loads(load(os.path.join(client.current_folder, CONANINFO)))
        self.assertEqual("language=0\nstatic=True", conan_info.options.dumps())

        # Try to upload and reuse the binaries
        client.run("upload Hello1/0.1@lasote/stable --all")
        self.assertEqual(str(client.user_io.out).count("Uploading package"), 1)

        client2 = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        client2.save(files3)

        client2.run("install .")
        self.assertNotIn("Package installed in Hello0/0.1", client2.user_io.out)
        self.assertNotIn("Building", client2.user_io.out)
        client2.run("build .")

        self.assertNotIn("libhello0.a", client2.user_io.out)
        self.assertNotIn("libhello1.a", client2.user_io.out)
        self.assertNotIn("libhello3.a", client2.user_io.out)
        client2.runner(command, cwd=client2.current_folder)

        self.assertEqual(['Hello Hello3', 'Hello Hello1', 'Hello Hello0'],
                         str(client2.user_io.out).splitlines()[-3:])

        # Issue 79, fixing private deps from current project
        files3 = cpp_hello_conan_files("Hello3", "0.2", ["Hello1/0.1@lasote/stable",
                                                         ("Hello0/0.1@lasote/stable", "private")],
                                       language=1)

        client2.save(files3, clean_first=True)
        client2.run('install . -o language=1 --build missing')
        client2.run('build .')
        self.assertNotIn("libhello0.a", client2.user_io.out)
        self.assertNotIn("libhello1.a", client2.user_io.out)
        self.assertNotIn("libhello3.a", client2.user_io.out)
        client2.runner(command, cwd=client2.current_folder)
        self.assertEqual(['Hola Hello3', 'Hola Hello1',
                          'Hola Hello0', 'Hola Hello0'],
                         str(client2.user_io.out).splitlines()[-4:])
