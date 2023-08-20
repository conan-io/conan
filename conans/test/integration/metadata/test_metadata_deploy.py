import textwrap

from conans.test.utils.tools import TestClient


class TestMetadataDeploy:
    """ prove we can gather metadata too with a deployer
    """

    def test_deploy(self):
        # FIXME: It only supports package metadata deployment, because missing internal interface
        conanfile = textwrap.dedent("""
            import os
            from conan import ConanFile
            from conan.tools.files import save, copy

            class Pkg(ConanFile):
                version = "0.1"

                def source(self):
                    save(self, os.path.join(self.recipe_metadata_folder, "logs", "src.log"),
                         f"srclog {self.name}!!")

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
                    shutil.copytree(d.package_metadata_folder, os.path.join(output_folder, "pkgs",
                                                                            d.ref.name))
                    # FIXME: Missing
                    #shutil.copytree(d.recipe_metadata_folder, os.path.join(output_folder, "pkgs",
                    #                                                         d.ref.name))
           """)

        c = TestClient()
        c.save({"conanfile.py": conanfile,
                "deploy.py": deploy})
        c.run("create . --name=pkg1")
        c.run("create . --name=pkg2")
        c.run("install --requires=pkg1/0.1 --requires=pkg2/0.1 --deployer=deploy")
        assert "some logs pkg1!!!" in c.load("pkgs/pkg1/logs/mylogs.txt")
        assert "some logs pkg2!!!" in c.load("pkgs/pkg2/logs/mylogs.txt")
        # TODO: This must pass
        # assert "srclog pkg1!!!" in c.load("recipes/pkg1/logs/src.log")
        # assert "srclog pkg2!!!" in c.load("recipes/pkg2/logs/src.log")
