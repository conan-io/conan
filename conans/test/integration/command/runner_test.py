import textwrap
import pytest
import docker
from conans.test.utils.tools import TestClient


def test_create_docker_runner():
    """
    Tests the ``conan create . ``
    """
    try:
        docker_client = docker.from_env()
        docker_client.images.get('conan-runner-default')
    except docker.errors.DockerException:
        pytest.skip("docker client not found")
    except docker.errors.ImageNotFound:
        pytest.skip("docker 'conan-runner-default' image doesn't exist")
    except docker.errors.APIError:
        pytest.skip("docker server returns an error")
    
    client = TestClient()
    profile_build = textwrap.dedent("""\
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
    image=conan-runner-default
    cache=copy
    remove=1
    """)
    profile_host = textwrap.dedent("""\
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
    image=conan-runner-default
    cache=copy
    remove=1
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
