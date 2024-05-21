from collections import OrderedDict

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestServer


class TestVersionRangesUpdatingTest:

    def test_update_remote(self):
        # https://github.com/conan-io/conan/issues/5333
        client = TestClient(light=True, default_server_user=True)
        client.save({"conanfile.py": GenConanfile("boost")})
        client.run("create . --version=1.69.0")
        client.run("create . --version=1.70.0")
        client.run("upload * -r=default --confirm")
        client.run("remove * -c")

        client.save({"conanfile.txt": "[requires]\nboost/[*]"}, clean_first=True)
        client.run("install .")
        assert "boost/1.70" in client.out
        assert "boost/1.69" not in client.out

        client.run("install .")
        assert "boost/1.70" in client.out
        assert "boost/1.69" not in client.out

        client.run("install . --update")
        assert "boost/1.70" in client.out
        assert "boost/1.69" not in client.out

    def test_update(self):
        client = TestClient(light=True, default_server_user=True)

        client.save({"pkg/conanfile.py": GenConanfile("pkg"),
                     "app/conanfile.py": GenConanfile().with_requirement("pkg/[~1]")})
        client.run("create pkg --version=1.1")
        client.run("create pkg --version=1.2")
        client.run("upload * -r=default --confirm")
        client.run("remove pkg/1.2* -c")

        client.run("install app")
        # Resolves to local package
        assert "pkg/1.1" in client.out
        assert "pkg/1.2" not in client.out

        client.run("install app --update")
        # Resolves to remote package
        assert "pkg/1.1" not in client.out
        assert "pkg/1.2" in client.out

        # newer in cache that in remotes and updating, should resolve the cache one
        client.run("create pkg --version=1.3")
        client.run("install app --update")
        assert "pkg/1.2" not in client.out
        assert "pkg/1.3" in client.out
        client.run("remove pkg/1.3* -c")

        # removes remote
        client.run("remove pkg* -r=default -c")
        # Resolves to local package
        client.run("install app")
        assert "pkg/1.1" not in client.out
        assert "pkg/1.2" in client.out

        client.run("install app --update")
        assert "pkg/1.1" not in client.out
        assert "pkg/1.2" in client.out


class TestVersionRangesMultiRemote:

    def test_multi_remote(self):
        servers = OrderedDict()
        servers["default"] = TestServer()
        servers["other"] = TestServer()
        client = TestClient(light=True, servers=servers, inputs=2*["admin", "password"])
        client.save({"hello0/conanfile.py": GenConanfile("hello0"),
                     "hello1/conanfile.py": GenConanfile("hello1").with_requires("hello0/[*]")})
        client.run("export hello0 --version=0.1")
        client.run("export hello0 --version=0.2")
        client.run("upload * -r=default -c")
        client.run("export hello0 --version=0.3")
        client.run("upload hello0/0.3 -r=other -c")
        client.run('remove "hello0/*" -c')

        client.run("install hello1 --build missing -r=default")
        assert "hello0/0.2" in client.out
        assert "hello0/0.3" not in client.out
        client.run("remove hello0/* -c")
        client.run("install hello1 --build missing -r=other")
        assert "hello0/0.2" not in client.out
        assert "hello0/0.3" in client.out
