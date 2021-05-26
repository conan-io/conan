import textwrap

from conans.model.ref import ConanFileReference
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.sources import gen_function_h, gen_function_cpp


def pkg_cmake(name, version, requires=None):
    refs = [ConanFileReference.loads(r) for r in requires or []]

    conanfile = textwrap.dedent("""\
        from conans import ConanFile
        from conan.tools.cmake import CMake
        class Pkg(ConanFile):
            name = "{name}"
            version = "{version}"
            exports = "*"
            {deps}
            settings = "os", "compiler", "arch", "build_type"
            generators = "CMakeToolchain", "CMakeDeps"

            def build(self):
                cmake = CMake(self)
                cmake.configure(source_folder="src")
                cmake.build()

            def package(self):
                self.copy("*.h", dst="include", src="src")
                self.copy("*.lib", dst="lib", keep_path=False)
                self.copy("*.dll", dst="bin", keep_path=False)
                self.copy("*.dylib*", dst="lib", keep_path=False)
                self.copy("*.so", dst="lib", keep_path=False)
                self.copy("*.a", dst="lib", keep_path=False)

            def package_info(self):
                self.cpp_info.libs = ["{name}"]
        """)
    deps = "requires = " + ", ".join('"{}"'.format(r) for r in requires) if requires else ""
    conanfile = conanfile.format(name=name, version=version, deps=deps)

    hdr = gen_function_h(name=name)
    deps = [r.name for r in refs]
    src = gen_function_cpp(name=name, includes=deps, calls=deps)
    cmake = gen_cmakelists(libname=name, libsources=["{}.cpp".format(name)], find_package=deps)

    return {"src/{}.h".format(name): hdr,
            "src/{}.cpp".format(name): src,
            "src/CMakeLists.txt": cmake,
            "conanfile.py": conanfile}
