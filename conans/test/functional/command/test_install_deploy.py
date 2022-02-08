import textwrap

import pytest

from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


@pytest.mark.tool("cmake")
def test_install_deploy():
    c = TestClient()
    c.run("new cmake_lib -d name=hello -d version=0.1")
    c.run("create .")
    cmake = gen_cmakelists(appname="my_app", appsources=["main.cpp"], find_package=["hello"])
    deploy = textwrap.dedent("""
        import os, shutil

        def deploy(conanfile, output_folder):
            for r, d in conanfile.dependencies.items():
                new_folder = os.path.join(output_folder, d.ref.name)
                shutil.copytree(d.package_folder, new_folder)
                d.set_deploy_folder(new_folder)
        """)
    c.save({"conanfile.txt": "[requires]\nhello/0.1",
            "deploy.py": deploy,
            "CMakeLists.txt": cmake,
            "main.cpp": gen_function_cpp(name="main", includes=["hello"], calls=["hello"])},
           clean_first=True)
    c.run("install . --deploy=deploy.py -of=mydeploy -g CMakeToolchain -g CMakeDeps")
    c.run("remove * -f")  # Make sure the cache is clean, no deps there
    cwd = c.current_folder.replace("\\", "/")
    deps = c.load("mydeploy/hello-release-x86_64-data.cmake")
    assert f'set(hello_PACKAGE_FOLDER_RELEASE "{cwd}/mydeploy/hello")' in deps
    assert 'set(hello_INCLUDE_DIRS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/include")' in deps
    assert 'set(hello_LIB_DIRS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/lib")' in deps

    # I can totally build without errors with deployed
    c.run_command("cmake . -DCMAKE_TOOLCHAIN_FILE=mydeploy/conan_toolchain.cmake")
    c.run_command("cmake --build . --config Release")
