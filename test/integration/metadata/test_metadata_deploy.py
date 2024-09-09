import os.path
import textwrap
from collections import OrderedDict

import pytest

from conan.test.utils.tools import TestClient, TestServer


class TestMetadataDeploy:
    """ prove we can gather metadata too with a deployer"""

    @pytest.fixture
    def client(self):
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import save, copy

            class Pkg(ConanFile):
                version = "0.1"

                def source(self):
                    save(self, os.path.join(self.recipe_metadata_folder, "logs", "src.log"),
                         f"srclog {self.name}!!!")

                def build(self):
                    save(self, "mylogs.txt", f"some logs {self.name}!!!")
                    copy(self, "mylogs.txt", src=self.build_folder,
                         dst=os.path.join(self.package_metadata_folder, "logs"))
            """)
        deploy = textwrap.dedent("""
            import os, shutil

            def deploy(graph, output_folder, **kwargs):
                conanfile = graph.root.conanfile
                for r, d in conanfile.dependencies.items():
                    if not os.path.exists(d.package_metadata_folder):
                        continue
                    shutil.copytree(d.package_metadata_folder, os.path.join(output_folder, "pkgs",
                                                                            d.ref.name))
                    shutil.copytree(d.recipe_metadata_folder, os.path.join(output_folder, "recipes",
                                                                             d.ref.name))
           """)

        servers = OrderedDict([("default", TestServer()), ("remote2", TestServer())])
        c = TestClient(servers=servers, inputs=2 * ["admin", "password"], light=True)
        c.save({"conanfile.py": conanfile,
                "deploy.py": deploy})
        c.run("create . --name=pkg1")
        c.run("create . --name=pkg2")
        return c

    def test_cache(self, client):
        c = client
        c.run("install --requires=pkg1/0.1 --requires=pkg2/0.1 --deployer=deploy")
        assert "some logs pkg1!!!" in c.load("pkgs/pkg1/logs/mylogs.txt")
        assert "some logs pkg2!!!" in c.load("pkgs/pkg2/logs/mylogs.txt")
        assert "srclog pkg1!!!" in c.load("recipes/pkg1/logs/src.log")
        assert "srclog pkg2!!!" in c.load("recipes/pkg2/logs/src.log")

    def test_remote(self, client):
        # But the remote story is more complex, metadata is not retrieved by default
        c = client
        c.run("upload * -c -r=default")
        c.run("remove * -c")
        # First install without metadata
        c.run("install --requires=pkg1/0.1 --requires=pkg2/0.1")
        # So this will not deploy metadata
        c.run("install --requires=pkg1/0.1 --requires=pkg2/0.1 --deployer=deploy -f=json",
              redirect_stdout="graph.json")
        assert not os.path.exists(os.path.join(c.current_folder, "pkgs"))

        # We can obtain the pkg-list for the graph, then "find-remote" and download the metadata
        c.run("list -g=graph.json -f=json", redirect_stdout="mylist.json")
        c.run("pkglist find-remote mylist.json -f=json", redirect_stdout="pkg_remotes.json")
        c.run("download --list=pkg_remotes.json -r=default --metadata=*")

        # Now we will have the metadata in cache and we can deploy it
        c.run("install --requires=pkg1/0.1 --requires=pkg2/0.1 --deployer=deploy")
        assert "some logs pkg1!!!" in c.load("pkgs/pkg1/logs/mylogs.txt")
        assert "some logs pkg2!!!" in c.load("pkgs/pkg2/logs/mylogs.txt")
        assert "srclog pkg1!!!" in c.load("recipes/pkg1/logs/src.log")
        assert "srclog pkg2!!!" in c.load("recipes/pkg2/logs/src.log")

    def test_multi_remote(self, client):
        # But the remote story is more complex, metadata is not retrieved by default,
        # we need to iterate the remotes if data coming from multiple remotes
        c = client
        c.run("upload pkg1* -c -r=default")
        c.run("upload pkg2* -c -r=remote2")
        c.run("remove * -c")
        # First install without metadata
        c.run("install --requires=pkg1/0.1 --requires=pkg2/0.1")
        # So this will not deploy metadata
        c.run("install --requires=pkg1/0.1 --requires=pkg2/0.1 --deployer=deploy -f=json",
              redirect_stdout="graph.json")
        assert not os.path.exists(os.path.join(c.current_folder, "pkgs"))

        # We can obtain the pkg-list for the graph, then "find-remote" and download the metadata
        c.run("list -g=graph.json -f=json", redirect_stdout="mylist.json")
        c.run("pkglist find-remote mylist.json -f=json", redirect_stdout="pkg_remotes.json")
        # we need to ITERATE the remotes
        c.run("download --list=pkg_remotes.json -r=default --metadata=*")
        c.run("download --list=pkg_remotes.json -r=remote2 --metadata=*")

        # Now we will have the metadata in cache and we can deploy it
        c.run("install --requires=pkg1/0.1 --requires=pkg2/0.1 --deployer=deploy")
        assert "some logs pkg1!!!" in c.load("pkgs/pkg1/logs/mylogs.txt")
        assert "some logs pkg2!!!" in c.load("pkgs/pkg2/logs/mylogs.txt")
        assert "srclog pkg1!!!" in c.load("recipes/pkg1/logs/src.log")
        assert "srclog pkg2!!!" in c.load("recipes/pkg2/logs/src.log")
