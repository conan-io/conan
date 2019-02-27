import unittest
from textwrap import dedent

from conans.test.utils.tools import TestClient
from conans.test.utils.conanfile import TestConanFile


class FullRevisionModeTest(unittest.TestCase):

    def full_revision_mode_test(self):
        clienta = TestClient()
        clienta.run("config set general.package_id_mode=full_revision_mode")
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

        clientb = TestClient(base_folder=clienta.base_folder)
        clientb.save({"conanfile.py": str(TestConanFile("libb", "0.1",
                                                        requires=["liba/0.1@user/testing"]))})
        clientb.run("create . user/testing")

        clientc = TestClient(base_folder=clienta.base_folder)
        clientc.save({"conanfile.py": str(TestConanFile("libc", "0.1",
                                                        requires=["libb/0.1@user/testing"]))})
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
        clientc.run("config set general.package_id_mode=full_package_revision_mode")
        clientc.run("install . user/testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientc.out)
        clientc.run("install . user/testing --build=libb")

        clienta.run("create . liba/0.1@user/testing")
        clientc.run("install . user/testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientc.out)
