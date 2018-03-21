import unittest

from conans.client.action_recorder import (ActionRecorder, INSTALL_ERROR_MISSING,
                                           INSTALL_ERROR_NETWORK)
from conans.model.ref import ConanFileReference, PackageReference


class TracerTest(unittest.TestCase):

    def setUp(self):
        self.ref1 = ConanFileReference.loads("lib1/1.0@conan/stable")
        self.ref2 = ConanFileReference.loads("lib2/1.0@conan/stable")
        self.ref3 = ConanFileReference.loads("lib3/1.0@conan/stable")

        self.ref_p1 = PackageReference(self.ref1, "1")
        self.ref_p2 = PackageReference(self.ref2, "2")
        self.ref_p3 = PackageReference(self.ref3, "3")

    def incomplete_process_test(self):
        tracer = ActionRecorder()
        tracer.recipe_install_error(self.ref1, INSTALL_ERROR_NETWORK, "SSL wtf", "http://drl.com")
        install_info = tracer.get_install_info()
        self.assertTrue(install_info["error"])
        self.assertIsNone(install_info["packages"][0]["package"])

    def test_install(self):
        tracer = ActionRecorder()
        tracer.recipe_fetched_from_cache(self.ref1)
        tracer.package_downloaded(self.ref_p1, "http://drl.com")
        tracer.recipe_downloaded(self.ref2, "http://drl.com")
        tracer.package_install_error(self.ref_p2, INSTALL_ERROR_MISSING, "no package found",
                                     remote="https://drl.com")

        tracer.recipe_fetched_from_cache(self.ref3)
        tracer.package_built(self.ref_p3, "", "")

        install_info = tracer.get_install_info()
        self.assertTrue(install_info["error"])

        first_installed = install_info["packages"][0]
        self.assertTrue(first_installed["recipe"]["cache"])
        self.assertFalse(first_installed["recipe"]["downloaded"])
        self.assertIsNone(first_installed["recipe"]["error"])
        self.assertEquals(str(first_installed["recipe"]["id"]), "lib1/1.0@conan/stable")

        self.assertFalse(first_installed["package"]["cache"])
        self.assertTrue(first_installed["package"]["downloaded"])
        self.assertIsNone(first_installed["package"]["error"])
        self.assertEquals(first_installed["package"]["remote"], 'http://drl.com')
        self.assertEquals(str(first_installed["package"]["id"]), "1")

        second_installed = install_info["packages"][1]
        self.assertFalse(second_installed["recipe"]["cache"])
        self.assertTrue(second_installed["recipe"]["downloaded"])
        self.assertIsNone(second_installed["recipe"]["error"])
        self.assertEquals(str(second_installed["recipe"]["id"]), "lib2/1.0@conan/stable")

        self.assertFalse(second_installed["package"]["cache"])
        self.assertEquals(second_installed["package"]["error"],
                          {'type': 'missing', 'description': 'no package found',
                           'remote': 'https://drl.com'})
        self.assertEquals(second_installed["package"]["remote"], 'https://drl.com')
        self.assertEquals(str(second_installed["package"]["id"]), "2")

        third_installed = install_info["packages"][2]
        self.assertFalse(third_installed["package"]["cache"])
        self.assertFalse(third_installed["package"]["error"])
        self.assertTrue(third_installed["package"]["built"])
        self.assertIsNone(third_installed["package"]["remote"])
        self.assertEquals(str(third_installed["package"]["id"]), "3")
