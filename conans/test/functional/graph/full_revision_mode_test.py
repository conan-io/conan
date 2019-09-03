import unittest
from textwrap import dedent

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, GenConanfile


class FullRevisionModeTest(unittest.TestCase):

    def recipe_revision_mode_test(self):
        liba_ref = ConanFileReference.loads("liba/0.1@user/testing")
        libb_ref = ConanFileReference.loads("libb/0.1@user/testing")

        clienta = TestClient()
        clienta.run("config set general.default_package_id_mode=recipe_revision_mode")
        conanfilea = dedent("""
            from conans import ConanFile
            from conans.tools import save
            import uuid, os
            class Pkg(ConanFile):
                def package(self):
                    save(os.path.join(self.package_folder, "file.txt"),
                         str(uuid.uuid1()))
            """)
        clienta.save({"conanfile.py": conanfilea})
        clienta.run("create . liba/0.1@user/testing")

        clientb = TestClient(cache_folder=clienta.cache_folder)
        clientb.save({"conanfile.py": GenConanfile().with_name("libb").with_version("0.1")
                                                    .with_require(liba_ref)})
        clientb.run("create . user/testing")

        clientc = TestClient(cache_folder=clienta.cache_folder)
        clientc.save({"conanfile.py": GenConanfile().with_name("libc").with_version("0.1")
                                                    .with_require(libb_ref)})
        clientc.run("install . user/testing")

        # Do a minor change to the recipe, it will change the recipe revision
        clienta.save({"conanfile.py": conanfilea + "# comment"})
        clienta.run("create . liba/0.1@user/testing")

        clientc.run("install . user/testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientc.out)
        # Building b with the new recipe revision of liba works
        clientc.run("install . user/testing --build=libb")

        # Now change only the package revision of liba
        clienta.run("create . liba/0.1@user/testing")
        clientc.run("install . user/testing")
        clientc.run("config set general.default_package_id_mode=package_revision_mode")
        clientc.run("install . user/testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientc.out)
        clientc.run("install . user/testing --build=libb")
        clientc.run("info . --build-order=ALL")

        clienta.run("create . liba/0.1@user/testing")
        clientc.run("install . user/testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientc.out)

        clienta.run("create . liba/0.1@user/testing")
        clientc.run("info . --build-order=ALL")

    def reusing_artifacts_after_build_test(self):
        # An unknown binary that after build results in the exact same PREF with PREV, doesn't
        # fire build of downstream
        client = TestClient()
        client.run("config set general.default_package_id_mode=package_revision_mode")
        conanfile = dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                pass
                %s
            """)
        client.save({"conanfile.py": conanfile % ""})
        client.run("create . liba/0.1@user/testing")

        client.save({"conanfile.py": conanfile % "requires = 'liba/0.1@user/testing'"})
        client.run("create . libb/0.1@user/testing")

        client.save({"conanfile.py": conanfile % "requires = 'libb/0.1@user/testing'"})
        # Telling to build LibA doesn't change the final result of LibA, which has same ID and PREV
        client.run("install . libd/0.1@user/testing --build=liba", assert_error=True)
        self.assertIn("liba/0.1@user/testing: Calling build()", client.out)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", client.out)
        self.assertIn("Package ID: Package_ID_unknown", client.out)
