import textwrap

from conans.model.ref import ConanFileReference
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.sources import gen_function_h, gen_function_cpp


def pkg_cmake(name, version, requires=None, exe=False):
    refs = [ConanFileReference.loads(r) for r in requires or []]
    pkg_name = name
    name = name.replace(".", "_")
    conanfile = textwrap.dedent("""\
        import os
        from conans import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class Pkg(ConanFile):
            name = "{pkg_name}"
            version = "{version}"
            exports_sources = "CMakeLists.txt", "src/*", "include/*"
            {deps}
            settings = "os", "compiler", "arch", "build_type"
            options = {{"shared": [True, False]}}
            default_options = {{"shared": False}}
            generators = "CMakeToolchain", "CMakeDeps"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                self.copy("*.h", dst="include", src="include")
                self.copy("*.lib", dst="lib", keep_path=False)
                self.copy("*.dll", dst="bin", keep_path=False)
                self.copy("*.dylib*", dst="lib", keep_path=False)
                self.copy("*.so", dst="lib", keep_path=False)
                self.copy("*.a", dst="lib", keep_path=False)
                self.copy("*app.exe", dst="bin", keep_path=False)
                self.copy("*app", dst="bin", keep_path=False)

            def package_info(self):
                self.cpp_info.libs = ["{name}"]
        """)
    deps = "requires = " + ", ".join('"{}"'.format(r) for r in requires) if requires else ""
    conanfile = conanfile.format(pkg_name=pkg_name, name=name, version=version, deps=deps)

    hdr = gen_function_h(name=name)
    deps = [r.name.replace(".", "_") for r in refs]
    src = gen_function_cpp(name=name, includes=deps, calls=deps)

    deps = [r.name for r in refs]
    files = {"include/{}.h".format(name): hdr,
             "src/{}.cpp".format(name): src,
             "conanfile.py": conanfile}
    if exe:
        src_app = gen_function_cpp(name="main", includes=[name], calls=[name])
        files["src/{}_app.cpp".format(name)] = src_app
        cmake = gen_cmakelists(appname="{}_app".format(name), appsources=["src/{}_app.cpp".format(name)],
                               libname=name, libsources=["src/{}.cpp".format(name)], find_package=deps)
    else:
        cmake = gen_cmakelists(libname=name, libsources=["src/{}.cpp".format(name)], find_package=deps)
    files["CMakeLists.txt"] = cmake
    return files


def pkg_cmake_test(require_name):
    conanfile = textwrap.dedent("""\
        import os
        from conans import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class Pkg(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            generators = "CMakeToolchain", "CMakeDeps", "VirtualRunEnv"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                cmd = os.path.join(self.cpp.build.bindir, "test")
                self.run(cmd, env="conanrun")
        """)

    deps = [require_name]
    src = gen_function_cpp(name="main", includes=deps, calls=deps)
    cmake = gen_cmakelists(appname="test", appsources=["src/test.cpp"], find_package=deps)

    return {"test_package/src/test.cpp": src,
            "test_package/CMakeLists.txt": cmake,
            "test_package/conanfile.py": conanfile}


def pkg_cmake_app(name, version, requires=None):
    refs = [ConanFileReference.loads(r) for r in requires or []]
    pkg_name = name
    name = name.replace(".", "_")
    conanfile = textwrap.dedent("""\
        import os
        from conans import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class Pkg(ConanFile):
            name = "{pkg_name}"
            version = "{version}"
            exports_sources = "CMakeLists.txt", "src/*"
            {deps}
            settings = "os", "compiler", "arch", "build_type"
            generators = "CMakeToolchain", "CMakeDeps"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                self.copy("*/app.exe", dst="bin", keep_path=False)
                self.copy("*app", dst="bin", keep_path=False)
        """)
    deps = "requires = " + ", ".join('"{}"'.format(r) for r in requires) if requires else ""
    conanfile = conanfile.format(pkg_name=pkg_name, name=name, version=version, deps=deps)

    deps = [r.name.replace(".", "_") for r in refs]
    src = gen_function_cpp(name="main", includes=deps, calls=deps)
    deps = [r.name for r in refs]
    cmake = gen_cmakelists(appname=name, appsources=["src/{}.cpp".format(name)], find_package=deps)

    return {"src/{}.cpp".format(name): src,
            "CMakeLists.txt": cmake,
            "conanfile.py": conanfile}
