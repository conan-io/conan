import unittest
from datetime import datetime

from conans.client.recorder.upload_recoder import UploadRecorder
from conans.model.ref import ConanFileReference, PackageReference


class UploadRecorderTest(unittest.TestCase):

    def setUp(self):
        self.upload_recorder = UploadRecorder()

    def test_empty(self):
        info = self.upload_recorder.get_info()
        expected_result = {'error': False, 'uploaded': []}
        self.assertEqual(expected_result, info)

    def test_sequential(self):
        ref = ConanFileReference.loads("fake/0.1@user/channel#rev")
        ref2 = ConanFileReference.loads("fakefake/0.1@user/channel")
        self.upload_recorder.add_recipe(ref, "my_remote", "https://fake_url.com")
        pref1 = PackageReference(ref, "fake_package_id", "prev")
        self.upload_recorder.add_package(pref1, "my_remote", "https://fake_url.com")
        self.upload_recorder.add_recipe(ref2, "my_remote2", "https://fake_url2.com")
        self.upload_recorder.add_package(PackageReference(ref2, "fakefake_package_id1"), "my_remote",
                                         "https://fake_url.com")
        self.upload_recorder.add_package(PackageReference(ref2, "fakefake_package_id2"), "my_remote",
                                         "https://fake_url.com")
        info = self.upload_recorder.get_info()
        expected_result_without_time = {
                                           "error": False,
                                           "uploaded": [
                                               {
                                                   "recipe": {
                                                       "id": "fake/0.1@user/channel",
                                                       "remote_name": "my_remote",
                                                       "remote_url": "https://fake_url.com",
                                                       "revision": "rev"
                                                       },
                                                   "packages": [
                                                       {
                                                           "id": "fake_package_id",
                                                           "remote_name": "my_remote",
                                                           "remote_url": "https://fake_url.com",
                                                           "revision": "prev"
                                                       }
                                                   ]
                                               },
                                               {
                                                   "recipe": {
                                                       "id": "fakefake/0.1@user/channel",
                                                       "remote_name": "my_remote2",
                                                       "remote_url": "https://fake_url2.com",
                                                   },
                                                   "packages": [
                                                       {
                                                           "id": "fakefake_package_id1",
                                                           "remote_name": "my_remote",
                                                           "remote_url": "https://fake_url.com"
                                                       },
                                                       {
                                                           "id": "fakefake_package_id2",
                                                           "remote_name": "my_remote",
                                                           "remote_url": "https://fake_url.com"
                                                       }
                                                   ]
                                               }
                                           ]
                                      }
        self._check_result(expected_result_without_time, info)

    def test_unordered(self):
        ref1 = ConanFileReference.loads("fake1/0.1@user/channel")
        ref2 = ConanFileReference.loads("fake2/0.1@user/channel")
        ref3 = ConanFileReference.loads("fake3/0.1@user/channel")
        self.upload_recorder.add_recipe(ref1, "my_remote1", "https://fake_url1.com")
        self.upload_recorder.add_recipe(ref2, "my_remote2", "https://fake_url2.com")
        self.upload_recorder.add_recipe(ref3, "my_remote3", "https://fake_url3.com")
        self.upload_recorder.add_package(PackageReference(ref1, "fake1_package_id1"), "my_remote1",
                                         "https://fake_url1.com")
        self.upload_recorder.add_package(PackageReference(ref2, "fake2_package_id1"), "my_remote2",
                                         "https://fake_url2.com")
        self.upload_recorder.add_package(PackageReference(ref2, "fake2_package_id2"), "my_remote2",
                                         "https://fake_url2.com")
        info = self.upload_recorder.get_info()
        expected_result_without_time = {
            "error": False,
            "uploaded": [
                {
                    "recipe": {
                        "id": "fake1/0.1@user/channel",
                        "remote_name": "my_remote1",
                        "remote_url": "https://fake_url1.com"
                    },
                    "packages": [
                        {
                            "id": "fake1_package_id1",
                            "remote_name": "my_remote1",
                            "remote_url": "https://fake_url1.com"
                        }
                    ]
                },
                {
                    "recipe": {
                        "id": "fake2/0.1@user/channel",
                        "remote_name": "my_remote2",
                        "remote_url": "https://fake_url2.com"
                    },
                    "packages": [
                        {
                            "id": "fake2_package_id1",
                            "remote_name": "my_remote2",
                            "remote_url": "https://fake_url2.com"
                        },
                        {
                            "id": "fake2_package_id2",
                            "remote_name": "my_remote2",
                            "remote_url": "https://fake_url2.com"
                        }
                    ]
                },
                {
                    "recipe": {
                        "id": "fake3/0.1@user/channel",
                        "remote_name": "my_remote3",
                        "remote_url": "https://fake_url3.com"
                    },
                    "packages": [
                    ]
                }
            ]
        }
        self._check_result(expected_result_without_time, info)

    def _check_result(self, expected, result):
        for i, item in enumerate(result["uploaded"]):
            assert item["recipe"]["time"]
            del result["uploaded"][i]["recipe"]["time"]

            for j, package in enumerate(item["packages"]):
                assert package["time"], datetime
                del result["uploaded"][i]["packages"][j]["time"]
        self.assertEqual(expected, result)
