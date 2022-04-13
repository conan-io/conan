import re
import textwrap

from conans.test.utils.tools import TestClient


def test_dll_location():
    t = TestClient()
    conanfile = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.files import save

    class Recipe(ConanFile):
        name = "dep"
        version = "1.0"
        options = {"shared": [True, False]}
        default_options = {"shared": False}
        def package(self):
            save(self, os.path.join(self.package_folder, "lib", "mylibrary.lib"), "")
            save(self, os.path.join(self.package_folder, "bin", "mylibrary.DLL"), "")

        def package_info(self):
            self.cpp_info.libs = ["mylibrary"]
    """)

    t.save({"dep/conanfile.py": conanfile})
    with t.chdir("dep"):
        t.run("create . -o shared=True -s:b os=Windows")

    t.run("install dep/1.0@ -g CMakeDeps -g CMakeToolchain -o dep:shared=True -s:b os=Windows")
    contents = t.load("dep-release-x86_64-data.cmake")
    assert 'set(dep_mylibrary_RELEASE_TYPE "SHARED")' in contents
    path = re.search(r'set\(dep_mylibrary_RELEASE_IMPLIB_PATH "(.*)"\)', contents).group(1)
    assert path.endswith("mylibrary.lib")
    path = re.search(r'set\(dep_mylibrary_RELEASE_IMPORTED_LOCATION "(.*)"\)', contents).group(1)
    assert path.endswith("mylibrary.DLL")

    # If the DLL name doesn't match we don't find it, so we adjust the IMPORTED_LOCATION to the lib
    t.save({"dep/conanfile.py": conanfile.replace("mylibrary.DLL", "muuuulibrary.DLL")})
    with t.chdir("dep"):
        t.run("create . -o shared=True -s:b os=Windows")

    t.run("install dep/1.0@ -g CMakeDeps -g CMakeToolchain -o dep:shared=True -s:b os=Windows")
    contents = t.load("dep-release-x86_64-data.cmake")
    assert 'set(dep_mylibrary_RELEASE_TYPE "SHARED")' in contents
    path = re.search(r'set\(dep_mylibrary_RELEASE_IMPORTED_LOCATION "(.*)"\)', contents).group(1)
    assert path.endswith("mylibrary.lib")
    assert "dep_mylibrary_RELEASE_IMPLIB_PATH" not in contents
