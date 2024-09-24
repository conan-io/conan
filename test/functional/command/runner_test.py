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


@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_cache_shared():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()
    profile_build = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)

    profile_host = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
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


@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_cache_shared_profile_from_cache():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()
    profile_build = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)

    profile_host = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
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

    client.save({"default_host": profile_host, "default_build": profile_build}, path=client.cache.profiles_path)
    client.run("new cmake_lib -d name=pkg -d version=0.2")
    client.run("create . -pr:h default_host -pr:b default_build")

    assert "[100%] Built target example" in client.out
    assert "Removing container" in client.out


@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_cache_shared_profile_folder():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()
    profile_build = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)

    profile_host = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
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

@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_dockerfile_folder_path():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()
    profile_build = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)

    profile_host_copy = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
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
    arch=x86_64
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


@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_profile_default_folder():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()
    profile_build = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)
    profile_host = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
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


@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_dockerfile_file_path():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()
    profile_build = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)
    profile_host = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
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


@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
@pytest.mark.parametrize("build_type,shared", [("Release", False), ("Debug", True)])
@pytest.mark.tool("ninja")
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
    arch=x86_64
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
    settings = "-s os=Linux -s arch=x86_64 -s build_type={} -o hello/*:shared={}".format(build_type, shared)
    # create should also work
    client.run("create . --name=hello --version=1.0 {} -pr:h=profile -pr:b=profile".format(settings))
    assert 'cmake -G "Ninja"' in client.out
    assert "main: {}!".format(build_type) in client.out

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
    arch=x86_64
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)
    profile_host = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
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


@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_from_configfile_with_args():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()
    configfile = textwrap.dedent(f"""
        image: conan-runner-default-test-with-args
        build:
            dockerfile: {dockerfile_path("Dockerfile_args")}
            build_context: {conan_base_path()}
            build_args:
                BASE_IMAGE: ubuntu:22.04
        run:
            name: my-conan-runner-container-with-args
        """)
    client.save({"configfile.yaml": configfile})


    profile_build = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
    build_type=Release
    compiler=gcc
    compiler.cppstd=gnu17
    compiler.libcxx=libstdc++11
    compiler.version=11
    os=Linux
    """)
    profile_host = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
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


@pytest.mark.skipif(docker_skip('ubuntu:22.04'), reason="Only docker running")
def test_create_docker_runner_default_build_profile():
    """
    Tests the ``conan create . ``
    """
    client = TestClient()

    profile_host = textwrap.dedent(f"""\
    [settings]
    arch=x86_64
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
    client.run("create . -pr:h host_clean")

    assert "Restore: pkg/0.2" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe" in client.out
    assert "Restore: pkg/0.2:8631cf963dbbb4d7a378a64a6fd1dc57558bc2fe metadata" in client.out
    assert "Removing container" in client.out
