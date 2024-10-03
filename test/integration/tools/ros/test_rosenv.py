import os
import textwrap
from sys import platform

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Uses UNIX commands")
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
    client.run_command(f"source \"{conanrosenv_path}\" && env")
    toolchain_path = os.path.join(client.current_folder, "install", "conan", "conan_toolchain.cmake")
    assert f"CMAKE_TOOLCHAIN_FILE={toolchain_path}" in client.out
    #TODO: Assert LD_LIBRARY_PATH/DYLD_LIBRARY_PATH/PATH paths are set in the environment
