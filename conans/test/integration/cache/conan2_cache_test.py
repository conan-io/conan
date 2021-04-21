import textwrap

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.scm import create_local_git_repo
from conans.test.utils.tools import TestClient


class TestCache:
    def test_conan_export(self):
        client = TestClient()
        client.run_command("open '{}'".format(client.cache_folder))
        client.save({"conanfile.py": GenConanfile().with_exports_sources("*"),
                     "source.txt": "somesource"})
        client.run("export . mypkg/1.0@user/channel")
        client.run("export . mypkg/2.0@user/channel")

        conanfile = GenConanfile().with_scm({"type": "git", "revision": "auto",
                                             "url": "auto"})
        path, _ = create_local_git_repo({"conanfile.py": str(conanfile),
                                         "source.txt": "somesource"})
        client.current_folder = path
        client.run("export . mypkg/3.0@user/channel")

    def test_conan_create(self):
        client = TestClient()
        client.run_command("open '{}'".format(client.cache_folder))
        client.save({"conanfile.py": GenConanfile().with_exports_sources("*"),
                     "source.txt": "somesource"})
        client.run("create . mypkg/1.0@user/channel")
        client.run("create . mypkg/2.0@user/channel")

        conanfile = GenConanfile().with_scm({"type": "git", "revision": "auto",
                                             "url": "auto"})
        path, _ = create_local_git_repo({"conanfile.py": str(conanfile),
                                         "source.txt": "somesource"})
        client.current_folder = path
        client.run("create . mypkg/3.0@user/channel")
