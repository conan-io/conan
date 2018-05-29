import unittest

from datetime import datetime
from conans.client.recorder.upload_recoder import UploadRecorder


class UploadRecorderTest(unittest.TestCase):

    def setUp(self):
        self.recorder = UploadRecorder()

    def empty_test(self):
        info = self.recorder.get_info()
        expected_result = {'error': False, 'uploaded': []}
        self.assertEqual(expected_result, info)

    def sequential_test(self):
        self.recorder.add_recipe("fake/0.1@user/channel", "my_remote", "https://fake_url.com")
        self.recorder.add_package("fake/0.1@user/channel", "fake_package_id")
        self.recorder.add_recipe("fakefake/0.1@user/channel", "my_remote2", "https://fake_url2.com")
        self.recorder.add_package("fakefake/0.1@user/channel", "fakefake_package_id1")
        self.recorder.add_package("fakefake/0.1@user/channel", "fakefake_package_id2")
        info = self.recorder.get_info()
        expected_result_without_time = {
                                           "error": False,
                                           "uploaded": [
                                               {
                                                   "recipe": {
                                                       "id": "fake/0.1@user/channel",
                                                       "remote_name": "my_remote",
                                                       "remote_url": "https://fake_url.com"
                                                       },
                                                   "packages": [
                                                       {
                                                           "id": "fake_package_id"
                                                       }
                                                   ]
                                               },
                                               {
                                                   "recipe": {
                                                       "id": "fakefake/0.1@user/channel",
                                                       "remote_name": "my_remote2",
                                                       "remote_url": "https://fake_url2.com"
                                                   },
                                                   "packages": [
                                                       {
                                                           "id": "fakefake_package_id1"
                                                       },
                                                       {
                                                           "id": "fakefake_package_id2"
                                                       }
                                                   ]
                                               }
                                           ]
                                      }

        self._check_result(expected_result_without_time, info)

    def unordered_test(self):
        self.recorder.add_recipe("fake1/0.1@user/channel", "my_remote1", "https://fake_url1.com")
        self.recorder.add_recipe("fake2/0.1@user/channel", "my_remote2", "https://fake_url2.com")
        self.recorder.add_recipe("fake3/0.1@user/channel", "my_remote3", "https://fake_url3.com")
        self.recorder.add_package("fake1/0.1@user/channel", "fake1_package_id1")
        self.recorder.add_package("fake2/0.1@user/channel", "fake2_package_id1")
        self.recorder.add_package("fake2/0.1@user/channel", "fake2_package_id2")
        info = self.recorder.get_info()
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
                            "id": "fake1_package_id1"
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
                            "id": "fake2_package_id1"
                        },
                        {
                            "id": "fake2_package_id2"
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

    def _check_result(self, expeceted, result):
        for i, item in enumerate(result["uploaded"]):
            assert item["recipe"]["time"]
            del result["uploaded"][i]["recipe"]["time"]

            for j, package in enumerate(item["packages"]):
                assert package["time"], datetime
                del result["uploaded"][i]["packages"][j]["time"]
        self.assertEqual(expeceted, result)
