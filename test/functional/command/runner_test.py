import textwrap
import os
import pytest
import docker
from conan.test.utils.tools import TestClient
from conan.test.assets.cmake import gen_cmakelists
from conan.test.assets.sources import gen_function_h, gen_function_cpp


def docker_skip(test_image=None):
    try:
        try:
            docker_client = docker.from_env()
        except:
            docker_client = docker.DockerClient(base_url=f'unix://{os.path.expanduser("~")}/.rd/docker.sock', version='auto') # Rancher
        if test_image:
            docker_client.images.pull(test_image)
    except docker.errors.DockerException:
        return True
    except docker.errors.ImageNotFound:
        return True
    except docker.errors.APIError:
        return True
    return False


def conan_base_path():
    import conans
    return os.path.dirname(os.path.dirname(conans.__file__))


def dockerfile_path(name=None):
    path = os.path.join(os.path.dirname(__file__), "dockerfiles")
    if name:
        path = os.path.join(path, name)
    return path


@pytest.mark.docker_runner
@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_cache_shared():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()
    profile_build = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)

    profile_host = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    [runner]
    type=docker
    dockerfile={dockerfile_path()}
    build_context={conan_base_path()}
    image=conan-runner-default-test
    cache=shared
    remove=True
    """)

    client.save({"host": profile_host, "build": profile_build})
    client.run("new cmake_lib -d name=pkg -d version=0.2")
    client.run("create . -pr:h host -pr:b build")

    assert "[100%] Built target example" in client.out
    assert "Removing container" in client.out


@pytest.mark.docker_runner
@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_cache_shared_profile_from_cache():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()
    profile_build = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)

    profile_host = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    [runner]
    type=docker
    dockerfile={dockerfile_path()}
    build_context={conan_base_path()}
    image=conan-runner-default-test
    cache=shared
    remove=True
    """)

    client.save({"default_host": profile_host, "default_build": profile_build}, path=client.paths.profiles_path)
    client.run("new cmake_lib -d name=pkg -d version=0.2")
    client.run("create . -pr:h default_host -pr:b default_build")

    assert "[100%] Built target example" in client.out
    assert "Removing container" in client.out


@pytest.mark.docker_runner
@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_cache_shared_profile_folder():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()
    profile_build = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)

    profile_host = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    [runner]
    type=docker
    dockerfile={dockerfile_path()}
    build_context={conan_base_path()}
    image=conan-runner-default-test
    cache=shared
    remove=True
    """)

    client.save({"build": profile_build})
    client.save({"docker_default": profile_host}, path = os.path.join(client.cache_folder, "profiles"))
    client.run("new cmake_lib -d name=pkg -d version=0.2")
    client.run("create . -pr:h docker_default -pr:b build")

    assert "[100%] Built target example" in client.out
    assert "Removing container" in client.out

@pytest.mark.docker_runner
@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_dockerfile_folder_path():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()
    profile_build = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)

    profile_host_copy = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    [runner]
    type=docker
    dockerfile={dockerfile_path()}
    build_context={conan_base_path()}
    image=conan-runner-default-test
    cache=copy
    remove=True
    """)

    profile_host_clean = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    [runner]
    type=docker
    dockerfile={dockerfile_path()}
    build_context={conan_base_path()}
    image=conan-runner-default-test
    cache=clean
    remove=True
    """)

    client.save({"host_copy": profile_host_copy, "host_clean": profile_host_clean, "build": profile_build})
    client.run("new cmake_lib -d name=pkg -d version=0.2")
    client.run("create . -pr:h host_copy -pr:b build")

    assert "Restore: pkg/0.2" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe metadata" in client.out
    assert "Removing container" in client.out

    client.run("create . -pr:h host_clean -pr:b build")

    assert "Restore: pkg/0.2" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe metadata" in client.out
    assert "Removing container" in client.out


@pytest.mark.docker_runner
@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_profile_default_folder():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()
    profile_build = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)
    profile_host = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    [runner]
    type=docker
    dockerfile={dockerfile_path("Dockerfile_test")}
    build_context={conan_base_path()}
    image=conan-runner-default-test
    cache=copy
    remove=True
    """)
    client.save({"host_from_profile": profile_host}, path = os.path.join(client.cache_folder, "profiles"))
    client.save({"build_from_profile": profile_build}, path = os.path.join(client.cache_folder, "profiles"))
    client.run("new cmake_lib -d name=pkg -d version=0.2")
    client.run("create . -pr:h host_from_profile -pr:b build_from_profile")

    assert "Container conan-runner-docker running" in client.out
    assert "Restore: pkg/0.2" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe metadata" in client.out
    assert "Removing container" in client.out


@pytest.mark.docker_runner
@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_dockerfile_file_path():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()
    profile_build = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)
    profile_host = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    [runner]
    type=docker
    dockerfile={dockerfile_path("Dockerfile_test")}
    build_context={conan_base_path()}
    image=conan-runner-default-test
    cache=copy
    remove=True
    """)
    client.save({"host": profile_host, "build": profile_build})
    client.run("new cmake_lib -d name=pkg -d version=0.2")
    client.run("create . -pr:h host -pr:b build")

    assert "Container conan-runner-docker running" in client.out
    assert "Restore: pkg/0.2" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe metadata" in client.out
    assert "Removing container" in client.out


@pytest.mark.docker_runner
@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
@pytest.mark.parametrize("build_type,shared", [("Release", False), ("Debug", True)])
def test_create_docker_runner_with_ninja(build_type, shared):
    conanfile = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.cmake import CMake, CMakeToolchain

    class Library(ConanFile):
        name = "hello"
        version = "1.0"
        settings = 'os', 'arch', 'compiler', 'build_type'
        exports_sources = 'hello.h', '*.cpp', 'CMakeLists.txt'
        options = {'shared': [True, False]}
        default_options = {'shared': False}

        def generate(self):
            tc = CMakeToolchain(self, generator="Ninja")
            tc.generate()

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()
            self.run(os.sep.join([".", "myapp"]))

        def package(self):
            cmake = CMake(self)
            cmake.install()
    """)

    client = TestClient(path_with_spaces=False)
    client.save({'conanfile.py': conanfile,
                "CMakeLists.txt": gen_cmakelists(libsources=["hello.cpp"],
                                                appsources=["main.cpp"],
                                                install=True),
                "hello.h": gen_function_h(name="hello"),
                "hello.cpp": gen_function_cpp(name="hello", includes=["hello"]),
                "main.cpp": gen_function_cpp(name="main", includes=["hello"],
                                            calls=["hello"])})
    profile = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    [runner]
    type=docker
    image=conan-runner-ninja-test
    dockerfile={dockerfile_path("Dockerfile_ninja")}
    build_context={conan_base_path()}
    cache=copy
    remove=True
    """)
    client.save({"profile": profile})
    settings = "-s os=Linux -s build_type={} -o hello/*:shared={}".format(build_type, shared)
    # create should also work
    client.run("create . --name=hello --version=1.0 {} -pr:h=profile -pr:b=profile".format(settings))
    assert 'cmake -G "Ninja"' in client.out
    assert "main: {}!".format(build_type) in client.out

@pytest.mark.docker_runner
@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_from_configfile():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()
    configfile = textwrap.dedent(f"""
        image: conan-runner-default-test
        build:
            dockerfile: {dockerfile_path("Dockerfile_test")}
            build_context: {conan_base_path()}
        run:
            name: my-custom-conan-runner-container
        """)
    client.save({"configfile.yaml": configfile})


    profile_build = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)
    profile_host = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    [runner]
    type=docker
    configfile={os.path.join(client.current_folder, 'configfile.yaml')}
    cache=copy
    remove=True
    """)

    client.save({"host": profile_host, "build": profile_build})
    client.run("new cmake_lib -d name=pkg -d version=0.2")
    client.run("create . -pr:h 'host' -pr:b 'build'")

    assert "Container my-custom-conan-runner-container running" in client.out
    assert "Restore: pkg/0.2" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe metadata" in client.out
    assert "Removing container" in client.out


@pytest.mark.docker_runner
@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_from_configfile_with_args():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()

    # Ensure the network exists
    docker_client = docker.from_env()
    docker_client.networks.create("my-network")

    configfile = textwrap.dedent(f"""
        image: conan-runner-default-test-with-args
        build:
            dockerfile: {dockerfile_path("Dockerfile_args")}
            build_context: {conan_base_path()}
            build_args:
                BASE_IMAGE: ubuntu:22.04
        run:
            name: my-conan-runner-container-with-args
            network: my-network
        """)
    client.save({"configfile.yaml": configfile})


    profile_build = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)
    profile_host = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    [runner]
    type=docker
    configfile={os.path.join(client.current_folder, 'configfile.yaml')}
    cache=copy
    remove=True
    """)

    client.save({"host": profile_host, "build": profile_build})
    client.run("new cmake_lib -d name=pkg -d version=0.2")
    client.run("create . -pr:h 'host' -pr:b 'build'")

    assert "command/dockerfiles/Dockerfile_args" in client.out
    assert "Restore: pkg/0.2" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe metadata" in client.out
    assert "Removing container" in client.out

    docker_client.networks.get("my-network").remove()

@pytest.mark.docker_runner
@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_default_build_profile():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()

    profile_host = textwrap.dedent(f"""\
    [settings]
    arch={{{{ detect_api.detect_arch() }}}}
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    [runner]
    type=docker
    dockerfile={dockerfile_path()}
    build_context={conan_base_path()}
    image=conan-runner-default-test
    cache=clean
    remove=True
    """)

    client.save({"host_clean": profile_host})
    client.run("new cmake_lib -d name=pkg -d version=0.2")
    client.run("create . -pr:h host_clean -vverbose")

    assert "Copying default profile" in client.out
    assert "Restore: pkg/0.2" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe metadata" in client.out
    assert "Removing container" in client.out


@pytest.mark.docker_runner
@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_in_subfolder():
    client = TestClient()
    conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.files import load, copy
        from conan.tools.cmake import CMake

        class Pkg(ConanFile):
            name = "pkg"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeToolchain"

            def layout(self):
                self.folders.root = ".."
                self.folders.source = "."
                self.folders.build = "build"

            def export_sources(self):
                folder = os.path.join(self.recipe_folder, "..")
                copy(self, "*.txt", folder, self.export_sources_folder)
                copy(self, "src/*.cpp", folder, self.export_sources_folder)
                copy(self, "include/*.h", folder, self.export_sources_folder)

            def source(self):
                cmake_file = load(self, "CMakeLists.txt")

            def build(self):
                path = os.path.join(self.source_folder, "CMakeLists.txt")
                cmake_file = load(self, path)
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                cmake = CMake(self)
                cmake.install()
            """)

    header = textwrap.dedent("""
        #pragma once
        void hello();
        """)
    source = textwrap.dedent("""
        #include <iostream>
        void hello() {
            std::cout << "Hello!" << std::endl;
        }
        """)

    cmakelist = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(pkg CXX)
        add_library(pkg src/hello.cpp)
        target_include_directories(pkg PUBLIC include)
        set_target_properties(pkg PROPERTIES PUBLIC_HEADER "include/hello.h")
        install(TARGETS pkg)

        """)

    profile_host = textwrap.dedent(f"""\
        [settings]
        arch={{{{ detect_api.detect_arch() }}}}
        build_type=Release
        compiler=gcc
        compiler.cppstd=gnu17
        compiler.libcxx=libstdc++11
        compiler.version=11
        os=Linux
        [runner]
        type=docker
        dockerfile={dockerfile_path()}
        build_context={conan_base_path()}
        image=conan-runner-default-test
        cache=clean
        remove=True
        """)

    client.save({"conan/conanfile.py": conanfile,
                "conan/host": profile_host,
                "include/hello.h": header,
                "src/hello.cpp": source,
                "CMakeLists.txt": cmakelist})

    with client.chdir("conan"):
        client.run("create . -pr:h host -vverbose")

    assert "Restore: pkg/1.0" in client.out
    assert "Removing container" in client.out
