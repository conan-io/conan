import unittest

from conans.client.recorder.action_recorder import (ActionRecorder, INSTALL_ERROR_MISSING,
                                                    INSTALL_ERROR_NETWORK)
from conans.model.ref import ConanFileReference, PackageReference


class ActionRecorderTest(unittest.TestCase):

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
        tracer.add_recipe_being_developed(self.ref1)
        install_info = tracer.get_info()
        self.assertTrue(install_info["error"])
        self.assertEquals(install_info["installed"][0]["packages"], [])
        self.assertEquals(install_info["installed"][0]["recipe"]["dependency"], False)

    def double_actions_test(self):
        tracer = ActionRecorder()
        tracer.recipe_downloaded(self.ref1, "http://drl.com")
        tracer.recipe_fetched_from_cache(self.ref1)
        tracer.package_downloaded(self.ref_p1, "http://drl.com")
        tracer.package_fetched_from_cache(self.ref_p1)

        install_info = tracer.get_info()
        self.assertFalse(install_info["error"])

        first_installed = install_info["installed"][0]
        self.assertFalse(first_installed["recipe"]["cache"])
        self.assertTrue(first_installed["recipe"]["downloaded"])
        self.assertIsNone(first_installed["recipe"]["error"])
        self.assertEquals(str(first_installed["recipe"]["id"]), "lib1/1.0@conan/stable")

        self.assertFalse(first_installed["packages"][0]["cache"])
        self.assertTrue(first_installed["packages"][0]["downloaded"])
        self.assertIsNone(first_installed["packages"][0]["error"])
        self.assertEquals(first_installed["packages"][0]["remote"], 'http://drl.com')
        self.assertEquals(str(first_installed["packages"][0]["id"]), "1")

    def test_install(self):
        tracer = ActionRecorder()
        tracer.recipe_fetched_from_cache(self.ref1)
        tracer.package_downloaded(self.ref_p1, "http://drl.com")
        tracer.recipe_downloaded(self.ref2, "http://drl.com")
        tracer.package_install_error(self.ref_p2, INSTALL_ERROR_MISSING, "no package found",
                                     remote_name="https://drl.com")

        tracer.recipe_fetched_from_cache(self.ref3)
        tracer.package_built(self.ref_p3)
        tracer.add_recipe_being_developed(self.ref1)

        install_info = tracer.get_info()
        self.assertTrue(install_info["error"])

        first_installed = install_info["installed"][0]

        self.assertTrue(first_installed["recipe"]["cache"])
        self.assertFalse(first_installed["recipe"]["dependency"])
        self.assertFalse(first_installed["recipe"]["downloaded"])
        self.assertIsNone(first_installed["recipe"]["error"])
        self.assertEquals(str(first_installed["recipe"]["id"]), "lib1/1.0@conan/stable")

        self.assertFalse(first_installed["packages"][0]["cache"])
        self.assertTrue(first_installed["packages"][0]["downloaded"])
        self.assertIsNone(first_installed["packages"][0]["error"])
        self.assertEquals(first_installed["packages"][0]["remote"], 'http://drl.com')
        self.assertEquals(str(first_installed["packages"][0]["id"]), "1")

        second_installed = install_info["installed"][1]
        self.assertFalse(second_installed["recipe"]["cache"])
        self.assertTrue(second_installed["recipe"]["dependency"])
        self.assertTrue(second_installed["recipe"]["downloaded"])
        self.assertIsNone(second_installed["recipe"]["error"])
        self.assertEquals(str(second_installed["recipe"]["id"]), "lib2/1.0@conan/stable")

        self.assertFalse(second_installed["packages"][0]["cache"])
        self.assertEquals(second_installed["packages"][0]["error"],
                          {'type': 'missing', 'description': 'no package found',
                           'remote': 'https://drl.com'})
        self.assertEquals(second_installed["packages"][0]["remote"], 'https://drl.com')
        self.assertEquals(str(second_installed["packages"][0]["id"]), "2")

        third_installed = install_info["installed"][2]
        self.assertTrue(third_installed["recipe"]["dependency"])
        self.assertFalse(third_installed["packages"][0]["cache"])
        self.assertFalse(third_installed["packages"][0]["error"])
        self.assertTrue(third_installed["packages"][0]["built"])
        self.assertIsNone(third_installed["packages"][0]["remote"])
        self.assertEquals(str(third_installed["packages"][0]["id"]), "3")
