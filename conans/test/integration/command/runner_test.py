import textwrap
import os
import pytest
import docker
from conans.test.utils.tools import TestClient
from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.sources import gen_function_h, gen_function_cpp



def docker_skip(test_image=None):
    try:
        docker_client = docker.from_env()
        if test_image:
            docker_client.images.get(test_image)
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


@pytest.mark.skipif(docker_skip(), reason="Only docker running")
@pytest.mark.xfail(reason="conan inside docker optional test")
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
    docker_build_context={conan_base_path()}
    image=conan-runner-default-test
    cache=copy
    remove=True
    """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class MyTest(ConanFile):
            name = "pkg"
            version = "0.2"
            settings = "build_type", "compiler"
            author = "John Doe"
            license = "MIT"
            url = "https://foo.bar.baz"
            homepage = "https://foo.bar.site"
            topics = "foo", "bar", "qux"
            provides = "libjpeg", "libjpg"
            deprecated = "other-pkg"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}
        """)
    client.save({"conanfile.py": conanfile, "host": profile_host, "build": profile_build})
    client.run("create . -pr:h host -pr:b build")

    assert "Restore: pkg/0.2" in client.out
    assert "Restore: pkg/0.2:a0826e5ee3b340fcc7a8ccde40224e3562316307" in client.out
    assert "Restore: pkg/0.2:a0826e5ee3b340fcc7a8ccde40224e3562316307 metadata" in client.out
    assert "Removing container" in client.out


@pytest.mark.skipif(docker_skip(), reason="Only docker running")
@pytest.mark.xfail(reason="conan inside docker optional test")
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
    docker_build_context={conan_base_path()}
    image=conan-runner-default-test
    cache=copy
    remove=True
    """)
    conanfile = textwrap.dedent("""
        from conan import ConanFile

        class MyTest(ConanFile):
            name = "pkg"
            version = "0.2"
            settings = "build_type", "compiler"
            author = "John Doe"
            license = "MIT"
            url = "https://foo.bar.baz"
            homepage = "https://foo.bar.site"
            topics = "foo", "bar", "qux"
            provides = "libjpeg", "libjpg"
            deprecated = "other-pkg"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}
        """)
    client.save({"conanfile.py": conanfile, "host": profile_host, "build": profile_build})
    client.run("create . -pr:h host -pr:b build")

    assert "Restore: pkg/0.2" in client.out
    assert "Restore: pkg/0.2:a0826e5ee3b340fcc7a8ccde40224e3562316307" in client.out
    assert "Restore: pkg/0.2:a0826e5ee3b340fcc7a8ccde40224e3562316307 metadata" in client.out
    assert "Removing container" in client.out


@pytest.mark.skipif(docker_skip(), reason="Only docker running")
@pytest.mark.xfail(reason="conan inside docker optional test")
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
    docker_build_context={conan_base_path()}
    cache=copy
    remove=True
    """)
    client.save({"profile": profile})
    settings = "-s os=Linux -s arch=x86_64 -s build_type={} -o hello/*:shared={}".format(build_type, shared)
    # create should also work
    client.run("create . --name=hello --version=1.0 {} -pr:h profile -pr:b profile".format(settings))
    print(client.out)
    assert 'cmake -G "Ninja"' in client.out
    assert "main: {}!".format(build_type) in client.out