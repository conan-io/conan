import unittest
from textwrap import dedent


from conans.model.recipe_ref import RecipeReference
from conan.test.utils.tools import TestClient, GenConanfile
from conans.util.files import save


class FullRevisionModeTest(unittest.TestCase):

    def test_recipe_revision_mode(self):
        liba_ref = RecipeReference.loads("liba/0.1@user/testing")
        libb_ref = RecipeReference.loads("libb/0.1@user/testing")

        clienta = TestClient()
        save(clienta.cache.new_config_path,
             "core.package_id:default_unknown_mode=recipe_revision_mode")
        conanfilea = dedent("""
            from conan import ConanFile
            from conan.tools.files import save
            import uuid, os
            class Pkg(ConanFile):
                def package(self):
                    save(self, os.path.join(self.package_folder, "file.txt"),
                         str(uuid.uuid1()))
            """)
        clienta.save({"conanfile.py": conanfilea})
        clienta.run("create . --name=liba --version=0.1 --user=user --channel=testing")

        clientb = TestClient(cache_folder=clienta.cache_folder)
        clientb.save({"conanfile.py": GenConanfile().with_name("libb").with_version("0.1")
                                                    .with_require(liba_ref)})
        clientb.run("create . --user=user --channel=testing")

        clientc = TestClient(cache_folder=clienta.cache_folder)
        clientc.save({"conanfile.py": GenConanfile().with_name("libc").with_version("0.1")
                                                    .with_require(libb_ref)})
        clientc.run("install . --user=user --channel=testing")

        # Do a minor change to the recipe, it will change the recipe revision
        clienta.save({"conanfile.py": conanfilea + "# comment"})
        clienta.run("create . --name=liba --version=0.1 --user=user --channel=testing")

        clientc.run("install . --user=user --channel=testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientc.out)
        # Building b with the new recipe revision of liba works
        clientc.run("install . --user=user --channel=testing --build=libb*")

        # Now change only the package revision of liba
        clienta.run("create . --name=liba --version=0.1 --user=user --channel=testing")
        clientc.run("install . --user=user --channel=testing")
