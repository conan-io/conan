import os
import platform
import shutil
import unittest

import pytest


from conans.test.assets.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import rmdir


@pytest.mark.slow
class SharedChainTest(unittest.TestCase):

    def setUp(self):
        self.servers = {"default": TestServer()}

    def _export_upload(self, name, version=None, deps=None):
        conan = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        files = cpp_hello_conan_files(name, version, deps, static=False)
        conan.save(files)

        conan.run("create . lasote/stable")
        conan.run("upload * --all --confirm")
        conan.run("remove * -f")
        rmdir(conan.current_folder)
        shutil.rmtree(conan.cache.store, ignore_errors=True)

    @pytest.mark.tool_compiler
    def test_uploaded_chain(self):
        self._export_upload("Hello0", "0.1")
        self._export_upload("Hello1", "0.1", ["Hello0/0.1@lasote/stable"])

        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        files = cpp_hello_conan_files("Hello2", "0.1", ["Hello1/0.1@lasote/stable"], static=True)
        c = files["conanfile.py"]
        #c = c.replace("def imports(self):", "def imports(self):\n"
        #                                    '        self.copy(pattern="*.so", dst=".", src="lib")')
        files["conanfile.py"] = c
        client.save(files)

        client.run("install .")
        client.run("build .")
        ld_path = (
            "LD_LIBRARY_PATH='{}' ".format(client.current_folder)
            if platform.system() != "Windows"
            else ""
        )
        p = os.sep.join([".", "bin", "say_hello"])
        client.run_command("ldd {}".format(p))
        print("**************Current", client.current_folder)
        print("**************Cache", client.cache_folder)
        print("**************LDD", client.out)
        command = ld_path + os.sep.join([".", "bin", "say_hello"])

        client.run_command(command)
        self.assertEqual(['Hello Hello2', 'Hello Hello1', 'Hello Hello0'],
                         str(client.out).splitlines()[-3:])


'''client = TestClient(default_server_user=True)
        # TODO: Move this to GenConanfile?
        conanfile = conanfile_sources_v2.format(name="hello0", version="0.1",
                                                package_name="hello0", configure="")
        cmake = cmake_v2.format(name="hello0")
        client.save({"src/hello0.h": gen_function_h(name="hello0"),
                     "src/hello0.cpp": gen_function_cpp(name="hello0", includes=["hello0"]),
                     "src/CMakeLists.txt": cmake,
                     "conanfile.py": conanfile})
        client.run("create . -o hello0:shared=True")

        conanfile = conanfile_sources_v2.format(name="hello1", version="0.1",
                                                package_name="hello1", configure="")
        conanfile
        cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project({name} CXX)

            add_library({name} {name}.cpp)
            target_link_libraries({name} {deps})
        """).format(name="hello1", deps="hello0")
        client.save({"src/hello1.h": gen_function_h(name="hello1"),
                     "src/hello1.cpp": gen_function_cpp(name="hello1", includes=["hello0", "hello1"],
                                                        calls=["hello0"]),
                     "src/CMakeLists.txt": cmake,
                     "conanfile.py": conanfile}, clean_first=True)
        client.run("create . -o hello1:shared=True")
        print(client.out)
        client.run("upload * --all --confirm")

        consumer = TestClient()
'''
