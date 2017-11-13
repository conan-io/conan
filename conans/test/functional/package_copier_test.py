import unittest
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.client.userio import UserIO
import sys
from conans.util.files import mkdir, save, load
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import SimplePaths
import os
from conans.client.cmd.copy import package_copy


class MockedBooleanUserIO(UserIO):

    def __init__(self, answer, ins=sys.stdin, out=None):
        self.answer = answer
        UserIO.__init__(self, ins, out)

    def request_boolean(self, msg, default_option=None):  # @UnusedVariable
        self.out.info(msg)
        return self.answer


class PackageCopierTest(unittest.TestCase):

    def test_copy(self):
        output = TestBufferConanOutput()
        userio = MockedBooleanUserIO(True, out=output)
        paths = SimplePaths(temp_folder())

        # Create some packages to copy
        reference = ConanFileReference.loads("Hello/0.1@lasote/testing")
        self._create_conanfile(reference, paths)
        self._create_package(reference, "0101001", paths)
        self._create_package(reference, "2222222", paths)

        # Copy all to destination
        package_copy(reference, "lasote/stable", ["0101001", "2222222"], paths,
                     user_io=userio, force=False)
        new_reference = ConanFileReference.loads("Hello/0.1@lasote/stable")
        self._assert_conanfile_exists(new_reference, paths)
        self._assert_package_exists(new_reference, "0101001", paths)
        self._assert_package_exists(new_reference, "2222222", paths)
        self.assertIn("Copied Hello/0.1@lasote/testing to Hello/0.1@lasote/stable", output)
        self.assertIn("Copied 0101001 to Hello/0.1@lasote/stable", output)
        self.assertIn("Copied 2222222 to Hello/0.1@lasote/stable", output)

        # Copy again, without force and answering yes
        output._stream.truncate(0)  # Reset output
        package_copy(reference, "lasote/stable", ["0101001", "2222222"], paths,
                     user_io=userio, force=False)
        self.assertIn("Copied Hello/0.1@lasote/testing to Hello/0.1@lasote/stable", output)
        self.assertIn("Copied 0101001 to Hello/0.1@lasote/stable", output)
        self.assertIn("Copied 2222222 to Hello/0.1@lasote/stable", output)
        self.assertIn("'Hello/0.1@lasote/stable' already exist. Override?", output)
        self.assertIn("Package '2222222' already exist. Override?", output)
        self.assertIn("Package '0101001' already exist. Override?", output)

        # Now alter the origin and copy again to same destination and confirm the copy
        self._create_conanfile(reference, paths, "new content")
        self._create_package(reference, "0101001", paths, "new lib content")
        self._create_package(reference, "2222222", paths, "new lib content")
        output._stream.truncate(0)  # Reset output
        package_copy(reference, "lasote/stable", ["0101001", "2222222"], paths,
                     user_io=userio, force=False)
        conanfile_content = load(os.path.join(paths.export(new_reference), "conanfile.py"))
        self.assertEquals(conanfile_content, "new content")
        package_content = load(os.path.join(paths.package(PackageReference(new_reference, "0101001")),
                                            "package.lib"))
        self.assertEquals(package_content, "new lib content")

        # Now we are going to answer always NO to override
        output._stream.truncate(0)  # Reset output
        userio = MockedBooleanUserIO(False, out=output)

        self._create_conanfile(reference, paths, "content22")
        self._create_package(reference, "0101001", paths, "newlib22")
        self._create_package(reference, "2222222", paths, "newlib22")
        package_copy(reference, "lasote/stable", ["0101001", "2222222"], paths,
                     user_io=userio, force=False)
        conanfile_content = load(os.path.join(paths.export(new_reference), "conanfile.py"))
        self.assertEquals(conanfile_content, "new content")  # Not content22
        p_ref = PackageReference(new_reference, "0101001")
        package_content = load(os.path.join(paths.package(p_ref), "package.lib"))
        self.assertEquals(package_content, "new lib content")  # Not newlib22
        # If conanfile is not override it exist
        self.assertNotIn("Package '2222222' already exist. Override?", output)
        self.assertNotIn("Package '0101001' already exist. Override?", output)
        self.assertNotIn("Copied 0101001 to Hello/0.1@lasote/stable", output)
        self.assertNotIn("Copied 2222222 to Hello/0.1@lasote/stable", output)

        # Now override
        output._stream.truncate(0)  # Reset output
        package_copy(reference, "lasote/stable", ["0101001", "2222222"], paths,
                     user_io=userio, force=True)
        self.assertIn("Copied 0101001 to Hello/0.1@lasote/stable", output)
        self.assertIn("Copied 2222222 to Hello/0.1@lasote/stable", output)

        # Now copy just one package to another user/channel
        output._stream.truncate(0)  # Reset output
        package_copy(reference, "pepe/mychannel", ["0101001"], paths,
                     user_io=userio, force=True)
        self.assertIn("Copied 0101001 to Hello/0.1@pepe/mychannel", output)
        self.assertNotIn("Copied 2222222 to Hello/0.1@pepe/mychannel", output)
        new_reference = ConanFileReference.loads("Hello/0.1@pepe/mychannel")
        self._assert_package_exists(new_reference, "0101001", paths)
        self._assert_package_doesnt_exists(new_reference, "2222222", paths)

    def _assert_conanfile_exists(self, reference, paths):
        self.assertTrue(os.path.exists(paths.conanfile(reference)))

    def _assert_package_exists(self, reference, package_id, paths):
        p1 = PackageReference(reference, package_id)
        self.assertTrue(os.path.exists(os.path.join(paths.package(p1), "package.lib")))

    def _assert_package_doesnt_exists(self, reference, package_id, paths):
        p1 = PackageReference(reference, package_id)
        self.assertFalse(os.path.exists(os.path.join(paths.package(p1), "package.lib")))

    def _create_conanfile(self, ref, paths, content="default_content"):
        origin_reg = paths.export(ref)
        mkdir(origin_reg)
        save(os.path.join(origin_reg, "conanfile.py"), content)
        mkdir(paths.export_sources(ref))

    def _create_package(self, ref, package_id, paths, content="default_content"):
        package1_ref = PackageReference(ref, package_id)
        package1_dir = paths.package(package1_ref)
        mkdir(package1_dir)
        save(os.path.join(package1_dir, "package.lib"), content)
