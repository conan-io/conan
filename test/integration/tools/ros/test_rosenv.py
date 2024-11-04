import os
import textwrap
import platform

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() == "Windows", reason="Uses UNIX commands")
def test_rosenv():
    """
    Test that the ROSEnv generator generates the environment files and that the environment variables are correctly set
    """
    client = TestClient()
    conanfile3 = textwrap.dedent('''
        [requires]
        [generators]
        CMakeDeps
        CMakeToolchain
        ROSEnv
        ''')
    client.save({
        "conanfile3.txt": conanfile3
    })

    client.run("install conanfile3.txt --output-folder install/conan")
    assert "Generated ROSEnv Conan file: conanrosenv.sh" in client.out
    install_folder = os.path.join(client.current_folder, "install", "conan")
    conanrosenv_path = os.path.join(install_folder, "conanrosenv.sh")
    assert os.path.exists(conanrosenv_path)
    conanrosenvbuild_path = os.path.join(install_folder, "conanrosenv-build.sh")
    assert os.path.exists(conanrosenvbuild_path)
    toolchain_path = os.path.join(client.current_folder, "install", "conan", "conan_toolchain.cmake")
    content = client.load(conanrosenvbuild_path)
    assert f'CMAKE_TOOLCHAIN_FILE="{toolchain_path}"' in content
    assert 'CMAKE_BUILD_TYPE="Release"' in content
    client.run_command(f'. "{conanrosenv_path}" && env')
    assert f"CMAKE_TOOLCHAIN_FILE={toolchain_path}" in client.out
    assert "CMAKE_BUILD_TYPE=Release" in client.out


@pytest.mark.skipif(platform.system() == "Windows", reason="Uses UNIX commands")
def test_rosenv_shared_libraries():
    """
    Test that the library paths env vars are set up correctly so that the executables built with
    colcon can found the shared libraries of conan packages
    """
    client = TestClient()
    c1 = GenConanfile("lib1", "1.0").with_shared_option(False).with_package_file("lib/lib1", "lib-content")
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
    conanrosenv_path = os.path.join(client.current_folder, "install", "conan", "conanrosenv.sh")
    client.run_command(f". \"{conanrosenv_path}\" && env")
    environment_content = client.out
    client.run(
        "cache path lib1/1.0#58723f478a96866dcbd9456d8eefd7c4:1744785cb24e3bdca70e27041dc5abd20476f947")
    lib1_lib_path = os.path.join(client.out.strip(), "lib")
    assert lib1_lib_path in environment_content
    client.run(
        "cache path lib2/1.0#4b7a6063ba107d770458ce10385beb52:5c3c2e56259489f7ffbc8e494921eda4b747ef21")
    lib2_lib_path = os.path.join(client.out.strip(), "lib")
    assert lib2_lib_path in environment_content
