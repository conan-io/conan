import os
import textwrap
import platform

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() == "Windows", reason="Uses UNIX commands")
def test_rosenv():
    """
    Test that the amentdeps generator generates conan_<name> folders and place CMake files
    in the correct path
    """
    client = TestClient()
    conanfile1 = textwrap.dedent('''
        import os
        from conan import ConanFile
        from conan.tools.files import save
        class Recipe(ConanFile):
            name = "lib1"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"

            def package(self):
                save(self, os.path.join(self.package_folder, "lib", "lib1"), "")
        ''')
    conanfile2 = textwrap.dedent('''
        import os
        from conan import ConanFile
        from conan.tools.files import save

        class Recipe(ConanFile):
            name = "lib2"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"

            def requirements(self):
                self.requires('lib1/1.0')

            def package(self):
                save(self, os.path.join(self.package_folder, "lib", "lib2"), "")
        ''')
    conanfile3 = textwrap.dedent('''
        [requires]
        lib2/1.0
        [generators]
        CMakeDeps
        CMakeToolchain
        ROSEnv
        ''')
    client.save({
        "conanfile1.py": conanfile1,
        "conanfile2.py": conanfile2,
        "conanfile3.txt": conanfile3
    })

    client.run("create conanfile1.py")
    client.run("create conanfile2.py")
    client.run("install conanfile3.txt --output-folder install/conan")
    assert "Generated ROSEnv Conan file: conanrosenv.bash" in client.out
    conanrosenv_path = os.path.join(client.current_folder, "install", "conan", "conanrosenv.bash")
    assert os.path.exists(conanrosenv_path)
    client.run_command(f". \"{conanrosenv_path}\" && env")
    toolchain_path = os.path.join(client.current_folder, "install", "conan", "conan_toolchain.cmake")
    assert f"CMAKE_TOOLCHAIN_FILE={toolchain_path}" in client.out
    assert "CMAKE_BUILD_TYPE=Release" in client.out


@pytest.mark.skipif(platform.system() == "Windows", reason="Uses UNIX commands")
def test_rosenv_shared_libraries():
    """
    Test that the library paths env vars are set up correctly so that the executables built with
    colcon can found the shared libraries of conan packages
    """
    client = TestClient()
    c1 = GenConanfile("lib1", "1.0").with_shared_option(False).with_package_file("lib/lib2", "lib-content")
    c2 = GenConanfile("lib2", "1.0").with_shared_option(False).with_requirement("lib1/1.0").with_package_file("lib/lib2", "lib-content")
    c3 = textwrap.dedent('''
           [requires]
           lib2/1.0
           [generators]
           CMakeDeps
           CMakeToolchain
           ROSEnv
           ''')
    client.save({
        "conanfile1.py": c1,
        "conanfile2.py": c2,
        "conanfile3.txt": c3
    })

    client.run("create conanfile1.py -o *:shared=True")
    client.run("create conanfile2.py -o *:shared=True")
    client.run("install conanfile3.txt -o *:shared=True --output-folder install/conan")
    conanrosenv_path = os.path.join(client.current_folder, "install", "conan", "conanrosenv.bash")
    client.run_command(f". \"{conanrosenv_path}\" && env")
    environment_content = client.out
    client.run(
        "cache path lib1/1.0#a77a22ae2a9a8dba9b408d95db4e9880:1744785cb24e3bdca70e27041dc5abd20476f947")
    lib1_lib_path = os.path.join(client.out.strip(), "lib")
    assert lib1_lib_path in environment_content
    client.run(
        "cache path lib2/1.0#4b7a6063ba107d770458ce10385beb52:5c3c2e56259489f7ffbc8e494921eda4b747ef21")
    lib2_lib_path = os.path.join(client.out.strip(), "lib")
    assert lib2_lib_path in environment_content


@pytest.mark.skipif(platform.system() == "Windows", reason="Uses UNIX commands")
def test_error_when_rosenv_not_used_with_cmake_generators():
    """
    ROSEnv generator should be used with CMake and CMakeToolchain generators
    """
    client = TestClient()
    c1 = GenConanfile("lib1", "1.0")
    c2 = textwrap.dedent('''
           [requires]
           lib2/1.0
           [generators]
           ROSEnv
           ''')
    client.save({
        "conanfile1.py": c1,
        "conanfile2.txt": c2
    })

    client.run("create conanfile1.py")
    client.run("install conanfile2.txt --output-folder install/conan")
    conanrosenv_path = os.path.join(client.current_folder, "install", "conan", "conanrosenv.bash")
    client.run_command(f". \"{conanrosenv_path}\" && env", assert_error=True)
    assert "kk" in client.out
