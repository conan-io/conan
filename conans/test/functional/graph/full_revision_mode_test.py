import unittest
from textwrap import dedent

from conans.test.utils.tools import TestClient
from conans.test.utils.conanfile import TestConanFile


class FullRevisionModeTest(unittest.TestCase):

    def full_revision_mode_test(self):
        clienta = TestClient()
        clienta.run("config set general.default_package_id_mode=full_revision_mode")
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
        clientc.run("config set general.default_package_id_mode=full_package_revision_mode")
        clientc.run("install . user/testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientc.out)
        clientc.run("install . user/testing --build=libb")
        clientc.run("info . --build-order=ALL")

        clienta.run("create . liba/0.1@user/testing")
        clientc.run("install . user/testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientc.out)

        clienta.run("create . liba/0.1@user/testing")
        clientc.run("info . --build-order=ALL")

    def binary_id_recomputation_after_build_test(self):
        clienta = TestClient()
        clienta.run("config set general.default_package_id_mode=full_revision_mode")
        conanfile = dedent("""
            from conans import ConanFile
            from conans.tools import save
            import uuid, os
            class Pkg(ConanFile):
                %s
                def package(self):
                    save(os.path.join(self.package_folder, "file.txt"),
                         str(uuid.uuid1()))
            """)
        clienta.save({"conanfile.py": conanfile % ""})
        clienta.run("create . liba/0.1@user/testing")

        clientb = TestClient(base_folder=clienta.base_folder)
        clientb.save({"conanfile.py": conanfile % "requires = 'liba/0.1@user/testing'"})
        clientb.run("config set general.default_package_id_mode=full_package_revision_mode")
        clientb.run("create . libb/0.1@user/testing")

        clientc = TestClient(base_folder=clienta.base_folder)
        clientc.save({"conanfile.py": conanfile % "requires = 'libb/0.1@user/testing'"})
        clientc.run("config set general.default_package_id_mode=full_package_revision_mode")
        clientc.run("create . libc/0.1@user/testing")

        clientd = TestClient(base_folder=clienta.base_folder)
        clientd.run("config set general.default_package_id_mode=full_package_revision_mode")
        clientd.save({"conanfile.py": conanfile % "requires = 'libc/0.1@user/testing'"})
        clientd.run("install . libd/0.1@user/testing")

        # Change A PREV
        clienta.run("create . liba/0.1@user/testing")
        clientd.run("install . libd/0.1@user/testing", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'libb/0.1@user/testing'", clientd.out)
        clientd.run("install . libd/0.1@user/testing --build=missing")

        self.assertIn("libc/0.1@user/testing: Unknown binary", clientd.out)
        self.assertIn("libc/0.1@user/testing: Updated ID", clientd.out)
        self.assertIn("libc/0.1@user/testing: Binary for updated ID from: Build", clientd.out)
        self.assertIn("libc/0.1@user/testing: Calling build()", clientd.out)

    def reusing_artifacts_after_build_test(self):
        # An unknown binary that after build results in the exact same PREF with PREV, doesn't
        # fire build of downstream
        client = TestClient()
        client.run("config set general.default_package_id_mode=full_package_revision_mode")
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
        client.run("create . libc/0.1@user/testing")

        client.save({"conanfile.py": conanfile % "requires = 'libc/0.1@user/testing'"})
        # Telling to build LibA doesn't change the final result of LibA, which has same ID and PREV
        client.run("install . libd/0.1@user/testing --build=liba")
        # So it is not necessary to build the downstream consumers of LibA
        for lib in ("libb", "libc"):
            self.assertIn("%s/0.1@user/testing: Unknown binary" % lib, client.out)
            self.assertIn("%s/0.1@user/testing: Updated ID" % lib, client.out)
            self.assertIn("%s/0.1@user/testing: Binary for updated ID from: Cache" % lib, client.out)
            self.assertIn("%s/0.1@user/testing: Already installed!" % lib, client.out)
