import os
import platform
import textwrap

from conans import load
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.sources import gen_function_cpp, gen_function_h
from conans.test.utils.tools import TestClient


def test_local_contents_and_generators():

    client = TestClient()
    client.run("new hello/1.0 -m=v2_cmake")
    client.run("create .")
    client.run("create . -s build_type=Debug")

    chat_lib = gen_function_cpp(name="chat", msg="blablabla", includes=["hello"], calls=["hello"])
    chat_hdr = gen_function_h(name="chat")
    chat_conanfile = textwrap.dedent("""
            from conans import ConanFile
            from conan.tools.cmake import CMake
            class App(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                requires = "hello/1.0"
                generators = "CMakeDeps", "CMakeToolchain"
                exports = "*"
                apply_env = False

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()

                def package(self):
                    self.copy(pattern="*.h", dst="include", keep_path=False)
                    self.copy(pattern="*.lib", dst="lib", keep_path=False, excludes="*say*")
                    self.copy(pattern="*lib*.a", dst="lib", keep_path=False)
                    self.copy(pattern="*.dll", dst="bin", keep_path=False)
                    self.copy(pattern="*.dylib", dst="lib", keep_path=False)
                    self.copy(pattern="*.so", dst="lib", keep_path=False)

                def package_info(self):
                    self.cpp_info.libs = ["chat"]
            """)
    chat_cmakelists = gen_cmakelists(libname="chat", libsources=["chat.cpp"],
                                     find_package=["hello"])
    client.save({"conanfile.py": chat_conanfile,
                 "CMakeLists.txt": chat_cmakelists,
                 "chat.cpp": chat_lib,
                 "chat.h": chat_hdr}, clean_first=True)
    client.run("create . chat/1.0@")
    client.run("create . chat/1.0@ -s build_type=Debug")

    consumer = str(GenConanfile().with_cmake_build().with_requirement("chat/1.0")
                   .with_import("from conan.tools.layout import cmake_layout"))
    consumer += """
    def layout(self):
        cmake_layout(self)
    """

    consumer_main = gen_function_cpp(name="main", msg="Consumer", includes=["chat"], calls=["chat"])
    consumer_cmakelists = gen_cmakelists(appname="chat", appsources=["main.cpp"],
                                         find_package=["chat"])
    client.save({"conanfile.py": consumer,
                 "CMakeLists.txt": consumer_cmakelists,
                 "main.cpp": consumer_main}, clean_first=True)

    client.run("install . --local-folder")
    client.run("install . --local-folder -s build_type=Debug")
    # WIPE THE CACHE! all to local
    client.remove_all()
    multi = platform.system() == "Windows"
    if not multi:
        for bt in ("Release", "Debug"):
            with client.chdir("cmake-build-{}".format(bt.lower())):
                client.run_command("cmake .. -D CMAKE_TOOLCHAIN_FILE=conan/conan_toolchain.cmake")
                client.run_command("cmake --build .")
                client.run_command("./chat")
                assert "Consumer: {}!".format(bt) in client.out
    else:
        # WIP
        pass
