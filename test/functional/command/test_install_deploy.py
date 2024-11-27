import os
import platform
import shutil
import textwrap

import pytest

from conan.test.assets.cmake import gen_cmakelists
from conan.test.assets.genconanfile import GenConanfile
from conan.test.assets.sources import gen_function_cpp
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conans.util.files import save


@pytest.fixture(scope="module")
def _client():
    c = TestClient()
    c.run("new cmake_lib -d name=hello -d version=0.1")
    c.run("create . -o *:shared=True -tf=")
    conanfile = textwrap.dedent("""
           import os
           from conan import ConanFile
           from conan.tools.files import save
           class Tool(ConanFile):
               name = "tool"
               version = "1.0"
               def package(self):
                   save(self, os.path.join(self.package_folder, "build", "my_tools.cmake"),
                        'set(MY_TOOL_VARIABLE "Hello world!")')

               def package_info(self):
                   self.cpp_info.includedirs = []
                   self.cpp_info.libdirs = []
                   self.cpp_info.bindirs = []
                   path_build_modules = os.path.join("build", "my_tools.cmake")
                   self.cpp_info.set_property("cmake_build_modules", [path_build_modules])
               """)
    c.save({"conanfile.py": conanfile}, clean_first=True)
    c.run("create .")
    return c


@pytest.fixture()
def client(_client):
    """ this is much faster than creating and uploading everythin
    """
    client = TestClient(default_server_user=True)
    shutil.rmtree(client.cache_folder)
    shutil.copytree(_client.cache_folder, client.cache_folder)
    return client


@pytest.mark.tool("cmake")
@pytest.mark.parametrize("powershell", [False, True])
def test_install_deploy(client, powershell):
    c = client
    custom_content = 'message(STATUS "MY_TOOL_VARIABLE=${MY_TOOL_VARIABLE}!")'
    cmake = gen_cmakelists(appname="my_app", appsources=["main.cpp"], find_package=["hello", "tool"],
                           custom_content=custom_content)
    deploy = textwrap.dedent("""
        import os, shutil

        # USE **KWARGS to be robust against changes
        def deploy(graph, output_folder, **kwargs):
            conanfile = graph.root.conanfile
            for r, d in conanfile.dependencies.items():
                new_folder = os.path.join(output_folder, d.ref.name)
                shutil.copytree(d.package_folder, new_folder)
                d.set_deploy_folder(new_folder)
        """)
    c.save({"conanfile.txt": "[requires]\nhello/0.1\ntool/1.0",
            "deploy.py": deploy,
            "CMakeLists.txt": cmake,
            "main.cpp": gen_function_cpp(name="main", includes=["hello"], calls=["hello"])},
           clean_first=True)
    pwsh = "-c tools.env.virtualenv:powershell=True" if powershell else ""
    c.run("install . -o *:shared=True "
          f"--deployer=deploy.py -of=mydeploy -g CMakeToolchain -g CMakeDeps {pwsh}")
    c.run("remove * -c")  # Make sure the cache is clean, no deps there
    arch = c.get_default_host_profile().settings['arch']
    deps = c.load(f"mydeploy/hello-release-{arch}-data.cmake")
    assert 'set(hello_PACKAGE_FOLDER_RELEASE "${CMAKE_CURRENT_LIST_DIR}/hello")' in deps
    assert 'set(hello_INCLUDE_DIRS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/include")' in deps
    assert 'set(hello_LIB_DIRS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/lib")' in deps

    # We can fully move it to another folder, and still works
    tmp = os.path.join(temp_folder(), "relocated")
    shutil.copytree(c.current_folder, tmp)
    shutil.rmtree(c.current_folder)
    c2 = TestClient(current_folder=tmp)
    # I can totally build without errors with deployed
    c2.run_command("cmake . -DCMAKE_TOOLCHAIN_FILE=mydeploy/conan_toolchain.cmake "
                   "-DCMAKE_BUILD_TYPE=Release")
    assert "MY_TOOL_VARIABLE=Hello world!!" in c2.out
    c2.run_command("cmake --build . --config Release")
    if platform.system() == "Windows":  # Only the .bat env-generators are relocatable
        if powershell:
            cmd = r"powershell.exe mydeploy\conanrun.ps1 ; Release\my_app.exe"
        else:
            cmd = r"mydeploy\conanrun.bat && Release\my_app.exe"
        # For Lunux: cmd = ". mydeploy/conanrun.sh && ./my_app"
        c2.run_command(cmd)
        assert "hello/0.1: Hello World Release!" in c2.out


@pytest.mark.tool("cmake")
def test_install_full_deploy_layout(client):
    c = client
    custom_content = 'message(STATUS "MY_TOOL_VARIABLE=${MY_TOOL_VARIABLE}!")'
    cmake = gen_cmakelists(appname="my_app", appsources=["main.cpp"], find_package=["hello", "tool"],
                           custom_content=custom_content)
    conanfile = textwrap.dedent("""
        [requires]
        hello/0.1
        tool/1.0
        [generators]
        CMakeDeps
        CMakeToolchain
        [layout]
        cmake_layout
        """)
    c.save({"conanfile.txt": conanfile,
            "CMakeLists.txt": cmake,
            "main.cpp": gen_function_cpp(name="main", includes=["hello"], calls=["hello"])},
           clean_first=True)
    c.run("install . -o *:shared=True --deployer=full_deploy.py")
    c.run("remove * -c")  # Make sure the cache is clean, no deps there
    arch = c.get_default_host_profile().settings['arch']
    folder = "/Release" if platform.system() != "Windows" else ""
    rel_path = "../../" if platform.system() == "Windows" else "../../../"
    deps = c.load(f"build{folder}/generators/hello-release-{arch}-data.cmake")
    assert 'set(hello_PACKAGE_FOLDER_RELEASE "${CMAKE_CURRENT_LIST_DIR}/' \
           f'{rel_path}full_deploy/host/hello/0.1/Release/{arch}")' in deps
    assert 'set(hello_INCLUDE_DIRS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/include")' in deps
    assert 'set(hello_LIB_DIRS_RELEASE "${hello_PACKAGE_FOLDER_RELEASE}/lib")' in deps

    # We can fully move it to another folder, and still works
    tmp = os.path.join(temp_folder(), "relocated")
    shutil.copytree(c.current_folder, tmp)
    shutil.rmtree(c.current_folder)
    c2 = TestClient(current_folder=tmp)
    with c2.chdir(f"build{folder}"):
        # I can totally build without errors with deployed
        cmakelist = "../.." if platform.system() != "Windows" else ".."
        c2.run_command(f"cmake {cmakelist} -DCMAKE_TOOLCHAIN_FILE=generators/conan_toolchain.cmake "
                       "-DCMAKE_BUILD_TYPE=Release")
        assert "MY_TOOL_VARIABLE=Hello world!!" in c2.out
        c2.run_command("cmake --build . --config Release")
        if platform.system() == "Windows":  # Only the .bat env-generators are relocatable atm
            cmd = r"generators\conanrun.bat && Release\my_app.exe"
            # For Lunux: cmd = ". mydeploy/conanrun.sh && ./my_app"
            c2.run_command(cmd)
            assert "hello/0.1: Hello World Release!" in c2.out


def test_copy_files_deploy():
    c = TestClient()
    deploy = textwrap.dedent("""
        import os, shutil

        def deploy(graph, output_folder, **kwargs):
            conanfile = graph.root.conanfile
            for r, d in conanfile.dependencies.items():
                bindir = os.path.join(d.package_folder, "bin")
                for f in os.listdir(bindir):
                    shutil.copy2(os.path.join(bindir, f), os.path.join(output_folder, f))
        """)
    c.save({"conanfile.txt": "[requires]\nhello/0.1",
            "deploy.py": deploy,
            "hello/conanfile.py": GenConanfile("hello", "0.1").with_package_file("bin/file.txt",
                                                                                 "content!!")})
    c.run("create hello")
    c.run("install . --deployer=deploy.py -of=mydeploy")


def test_multi_deploy():
    """ check that we can add more than 1 deployer in the command line, both in local folders
    and in cache.
    Also testing that using .py extension or not, is the same
    Also, the local folder have precedence over the cache extensions
    """
    c = TestClient()
    deploy1 = textwrap.dedent("""
        def deploy(graph, output_folder, **kwargs):
            conanfile = graph.root.conanfile
            conanfile.output.info("deploy1!!")
        """)
    deploy2 = textwrap.dedent("""
        def deploy(graph, output_folder, **kwargs):
            conanfile = graph.root.conanfile
            conanfile.output.info("sub/deploy2!!")
        """)
    deploy_cache = textwrap.dedent("""
        def deploy(graph, output_folder, **kwargs):
            conanfile = graph.root.conanfile
            conanfile.output.info("deploy cache!!")
        """)
    save(os.path.join(c.cache_folder, "extensions", "deploy", "deploy_cache.py"), deploy_cache)
    # This should never be called in this test, always the local is found first
    save(os.path.join(c.cache_folder, "extensions", "deploy", "mydeploy.py"), "CRASH!!!!")
    c.save({"conanfile.txt": "",
            "mydeploy.py": deploy1,
            "sub/mydeploy2.py": deploy2})

    c.run("install . --deployer=mydeploy --deployer=sub/mydeploy2 --deployer=deploy_cache")
    assert "conanfile.txt: deploy1!!" in c.out
    assert "conanfile.txt: sub/deploy2!!" in c.out
    assert "conanfile.txt: deploy cache!!" in c.out

    # Now with .py extension
    c.run("install . --deployer=mydeploy.py --deployer=sub/mydeploy2.py --deployer=deploy_cache.py")
    assert "conanfile.txt: deploy1!!" in c.out
    assert "conanfile.txt: sub/deploy2!!" in c.out
    assert "conanfile.txt: deploy cache!!" in c.out


def test_deploy_local_import():
    """ test that deployers can share some Python code with local imports
    """
    c = TestClient()
    helper = textwrap.dedent("""
        def myhelper(conanfile):
            conanfile.output.info("My HELPER!!")
        """)
    deploy_cache = textwrap.dedent("""
        from helper import myhelper
        def deploy(graph, output_folder, **kwargs):
            myhelper(graph.root.conanfile)
        """)
    save(os.path.join(c.cache_folder, "extensions", "deployers", "deploy_cache.py"), deploy_cache)
    save(os.path.join(c.cache_folder, "extensions", "deployers", "helper.py"), helper)
    c.save({"conanfile.txt": ""})
    c.run("install . --deployer=deploy_cache")
    assert "conanfile.txt: My HELPER!!" in c.out


def test_builtin_full_deploy():
    """ check the built-in full_deploy
    """
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import save
        class Pkg(ConanFile):
            settings = "arch", "build_type"
            def package(self):
                content = f"{self.settings.build_type}-{self.settings.arch}"
                save(self, os.path.join(self.package_folder, "include/hello.h"), content)

            def package_info(self):
                path_build_modules = os.path.join("build", "my_tools_{}.cmake".format(self.context))
                self.cpp_info.set_property("cmake_build_modules", [path_build_modules])
            """)
    c.save({"conanfile.py": conanfile})
    c.run("create . --name=dep --version=0.1")
    c.run("create . --name=dep --version=0.1 -s build_type=Debug -s arch=x86")
    c.save({"conanfile.txt": "[requires]\ndep/0.1"}, clean_first=True)
    c.run("install . --deployer=full_deploy -of=output -g CMakeDeps")
    assert "Conan built-in full deployer" in c.out
    c.run("install . --deployer=full_deploy -of=output -g CMakeDeps "
          "-s build_type=Debug -s arch=x86")

    host_arch = c.get_default_host_profile().settings['arch']
    release = c.load(f"output/full_deploy/host/dep/0.1/Release/{host_arch}/include/hello.h")
    assert f"Release-{host_arch}" in release
    debug = c.load("output/full_deploy/host/dep/0.1/Debug/x86/include/hello.h")
    assert "Debug-x86" in debug
    cmake_release = c.load(f"output/dep-release-{host_arch}-data.cmake")
    assert 'set(dep_INCLUDE_DIRS_RELEASE "${dep_PACKAGE_FOLDER_RELEASE}/include")' in cmake_release
    assert f"${{CMAKE_CURRENT_LIST_DIR}}/full_deploy/host/dep/0.1/Release/{host_arch}" in cmake_release
    assert 'set(dep_BUILD_MODULES_PATHS_RELEASE ' \
           '"${dep_PACKAGE_FOLDER_RELEASE}/build/my_tools_host.cmake")' in cmake_release
    cmake_debug = c.load("output/dep-debug-x86-data.cmake")
    assert 'set(dep_INCLUDE_DIRS_DEBUG "${dep_PACKAGE_FOLDER_DEBUG}/include")' in cmake_debug
    assert "${CMAKE_CURRENT_LIST_DIR}/full_deploy/host/dep/0.1/Debug/x86" in cmake_debug
    assert 'set(dep_BUILD_MODULES_PATHS_DEBUG ' \
           '"${dep_PACKAGE_FOLDER_DEBUG}/build/my_tools_host.cmake")' in cmake_debug


def test_deploy_reference():
    """ check that we can also deploy a reference
    """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_package_file("include/hi.h", "hi")})
    c.run("create .")

    c.run("install  --requires=pkg/1.0 --deployer=full_deploy --output-folder=output")
    # NOTE: Full deployer always use build_type/arch, even if None/None in the path, same structure
    header = c.load("output/full_deploy/host/pkg/1.0/include/hi.h")
    assert "hi" in header

    # Testing that we can deploy to the current folder too
    c.save({}, clean_first=True)
    c.run("install  --requires=pkg/1.0 --deployer=full_deploy")
    # NOTE: Full deployer always use build_type/arch, even if None/None in the path, same structure
    header = c.load("full_deploy/host/pkg/1.0/include/hi.h")
    assert "hi" in header


def test_deploy_overwrite():
    """ calling several times the install --deploy doesn't crash if files already exist
    """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_package_file("include/hi.h", "hi")})
    c.run("create .")

    c.run("install  --requires=pkg/1.0 --deployer=full_deploy --output-folder=output")
    header = c.load("output/full_deploy/host/pkg/1.0/include/hi.h")
    assert "hi" in header

    # modify the package
    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_package_file("include/hi.h", "bye")})
    c.run("create .")
    c.run("install  --requires=pkg/1.0 --deployer=full_deploy --output-folder=output")
    header = c.load("output/full_deploy/host/pkg/1.0/include/hi.h")
    assert "bye" in header


def test_deploy_editable():
    """ when deploying something that is editable, with the full_deploy built-in, it will copy the
    editable files as-is, but it doesn't fail at this moment
    """

    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0"),
            "src/include/hi.h": "hi"})
    c.run("editable add .")

    # If we don't change to another folder, the full_deploy will be recursive and fail
    with c.chdir(temp_folder()):
        c.run("install  --requires=pkg/1.0 --deployer=full_deploy --output-folder=output")
        header = c.load("output/full_deploy/host/pkg/1.0/src/include/hi.h")
        assert "hi" in header


def test_deploy_aggregate_components():
    """
    The caching of aggregated components can be causing issues when deploying and using
    generators that would still point to the packages with components in the cache
    https://github.com/conan-io/conan/issues/14022
    """
    c = TestClient()
    dep = textwrap.dedent("""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "dep"
            version = "0.1"

            def package_info(self):
                self.cpp_info.components["mycomp"].libs = ["mycomp"]
            """)
    c.save({"dep/conanfile.py": dep,
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_settings("build_type")
                                                          .with_requires("dep/0.1")
                                                          .with_generator("CMakeDeps"),
            "consumer/conanfile.py": GenConanfile().with_settings("build_type")
                                                   .with_requires("pkg/0.1")
                                                   .with_generator("CMakeDeps")})
    c.run("export dep")
    c.run("export pkg")

    # If we don't change to another folder, the full_deploy will be recursive and fail
    c.run("install consumer --build=missing --deployer=full_deploy --output-folder=output")
    data = c.load("output/dep-release-data.cmake")
    assert 'set(dep_PACKAGE_FOLDER_RELEASE ' \
           '"${CMAKE_CURRENT_LIST_DIR}/full_deploy/host/dep/0.1")' in data
    assert 'set(dep_INCLUDE_DIRS_RELEASE "${dep_PACKAGE_FOLDER_RELEASE}/include")' in data


def test_deploy_single_package():
    """ Let's try a deploy that executes on a single package reference
    """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_package_file("include/hi.h", "hi"),
            "consumer/conanfile.txt": "[requires]\npkg/1.0"})
    c.run("create .")

    # if we deploy one --requires, we get that package
    c.run("install  --requires=pkg/1.0 --deployer=direct_deploy --output-folder=output")
    header = c.load("output/direct_deploy/pkg/include/hi.h")
    assert "hi" in header

    # If we deploy a local conanfile.txt, we get deployed its direct dependencies
    c.run("install consumer/conanfile.txt --deployer=direct_deploy --output-folder=output2")
    header = c.load("output2/direct_deploy/pkg/include/hi.h")
    assert "hi" in header


def test_deploy_output_locations():
    tc = TestClient()
    deployer = textwrap.dedent("""
    def deploy(graph, output_folder, **kwargs):
        graph.root.conanfile.output.info(f"Deployer output: {output_folder}")
    """)
    tc.save({"conanfile.txt": "",
             "my_deploy.py": deployer})

    tmp_folder = temp_folder()
    tc.run(f"install . --deployer=my_deploy -of='{tmp_folder}'")
    assert f"Deployer output: {tmp_folder}" in tc.out

    deployer_output = temp_folder()
    tc.run(f"install . --deployer=my_deploy -of='{tmp_folder}' --deployer-folder='{deployer_output}'")
    assert f"Deployer output: {deployer_output}" in tc.out
    assert f"Deployer output: {tmp_folder}" not in tc.out


def test_not_deploy_absolute_paths():
    """ Absolute paths, for system packages, don't need to be relativized
    https://github.com/conan-io/conan/issues/15242
    """
    c = TestClient()
    some_abs_path = temp_folder().replace("\\", "/")
    conanfile = textwrap.dedent(f"""
        from conan import ConanFile
        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"
            def package_info(self):
                self.cpp_info.includedirs = ["{some_abs_path}/myusr/include"]
                self.cpp_info.libdirs = ["{some_abs_path}/myusr/lib"]
                self.buildenv_info.define_path("MYPATH", "{some_abs_path}/mypath")
        """)
    c.save({"conanfile.py": conanfile})
    c.run("create .")

    # if we deploy one --requires, we get that package
    c.run("install  --requires=pkg/1.0 --deployer=full_deploy -g CMakeDeps -g CMakeToolchain "
          "-s os=Linux -s:b os=Linux -s arch=x86_64 -s:b arch=x86_64")
    data = c.load("pkg-release-x86_64-data.cmake")
    assert f'set(pkg_INCLUDE_DIRS_RELEASE "{some_abs_path}/myusr/include")' in data
    assert f'set(pkg_LIB_DIRS_RELEASE "{some_abs_path}/myusr/lib")' in data

    env = c.load("conanbuildenv-release-x86_64.sh")
    assert f'export MYPATH="{some_abs_path}/mypath"' in env


def test_deploy_incorrect_folder():
    # https://github.com/conan-io/cmake-conan/issues/658
    c = TestClient()
    c.save({"conanfile.txt": ""})
    c.run('install . --deployer=full_deploy --deployer-folder="mydep fold"')
    assert os.path.exists(os.path.join(c.current_folder, "mydep fold"))
    if platform.system() == "Windows":  # This only fails in Windows
        c.run(r'install . --deployer=full_deploy --deployer-folder="\"mydep fold\""',
              assert_error=True)
        assert "ERROR: Deployer folder cannot be created" in c.out


class TestRuntimeDeployer:
    def test_runtime_deploy(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.tools.files import copy
           class Pkg(ConanFile):
               package_type = "shared-library"
               def package(self):
                   copy(self, "*.so", src=self.build_folder, dst=self.package_folder)
                   copy(self, "*.dll", src=self.build_folder, dst=self.package_folder)
           """)
        c.save({"pkga/conanfile.py": conanfile,
                "pkga/lib/pkga.so": "",
                "pkga/bin/pkga.dll": "",
                "pkgb/conanfile.py": conanfile,
                "pkgb/lib/pkgb.so": ""})
        c.run("export-pkg pkga --name=pkga --version=1.0")
        c.run("export-pkg pkgb --name=pkgb --version=1.0")
        c.run("install --requires=pkga/1.0 --requires=pkgb/1.0 --deployer=runtime_deploy "
              "--deployer-folder=myruntime -vvv")

        expected = sorted(["pkga.so", "pkgb.so", "pkga.dll"])
        assert sorted(os.listdir(os.path.join(c.current_folder, "myruntime"))) == expected

    def test_runtime_not_deploy(self):
        # https://github.com/conan-io/conan/issues/16712
        # If no run=False (no package-type), then no runtime is deployed
        c = TestClient()
        conanfile = textwrap.dedent("""
           from conan import ConanFile
           from conan.tools.files import copy
           class Pkg(ConanFile):
               def package(self):
                   copy(self, "*.so", src=self.build_folder, dst=self.package_folder)
                   copy(self, "*.dll", src=self.build_folder, dst=self.package_folder)
           """)
        c.save({"pkga/conanfile.py": conanfile,
                "pkga/lib/pkga.so": "",
                "pkga/bin/pkga.dll": ""})
        c.run("export-pkg pkga --name=pkga --version=1.0")
        c.run("install --requires=pkga/1.0 --deployer=runtime_deploy --deployer-folder=myruntime")
        assert os.listdir(os.path.join(c.current_folder, "myruntime")) == []

    def test_runtime_deploy_components(self):
        c = TestClient()
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import copy
            class Pkg(ConanFile):
               package_type = "shared-library"
               def package(self):
                   copy(self, "*.so", src=self.build_folder,
                        dst=os.path.join(self.package_folder, "a"))
                   copy(self, "*.dll", src=self.build_folder,
                        dst=os.path.join(self.package_folder, "b"))
               def package_info(self):
                   self.cpp_info.components["a"].libdirs = ["a"]
                   self.cpp_info.components["b"].bindirs = ["b"]
           """)
        c.save({"pkga/conanfile.py": conanfile,
                "pkga/lib/pkga.so": "",
                "pkga/bin/pkga.dll": "",
                "pkgb/conanfile.py": conanfile,
                "pkgb/lib/pkgb.so": ""})
        c.run("export-pkg pkga --name=pkga --version=1.0")
        c.run("export-pkg pkgb --name=pkgb --version=1.0")
        c.run("install --requires=pkga/1.0 --requires=pkgb/1.0 --deployer=runtime_deploy "
              "--deployer-folder=myruntime -vvv")

        expected = sorted(["pkga.so", "pkgb.so", "pkga.dll"])
        assert sorted(os.listdir(os.path.join(c.current_folder, "myruntime"))) == expected


def test_deployer_errors():
    c = TestClient()
    c.save({"conanfile.txt": "",
            "mydeploy.py": "",
            "mydeploy2.py": "nonsense"})
    c.run("install . --deployer=nonexisting.py", assert_error=True)
    assert "ERROR: Cannot find deployer 'nonexisting.py'" in c.out
    c.run("install . --deployer=mydeploy.py", assert_error=True)
    assert "ERROR: Deployer does not contain 'deploy()' function" in c.out
    c.run("install . --deployer=mydeploy2.py", assert_error=True)
    # The error message says conanfile, not a big deal still path to file is shown
    assert "ERROR: Unable to load conanfile" in c.out
