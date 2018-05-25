import unittest

from conans.client.recorder.search_recorder import SearchRecorder


class SearchRecorderTest(unittest.TestCase):

    def setUp(self):
        self.recorder = SearchRecorder()

    def empty_test(self):
        info = self.recorder.get_info()
        expected_result = {'error': False, 'results': []}
        self.assertEqual(expected_result, info)

    def sequential_test(self):
        self.recorder.add_recipe("remote1", "fake/0.1@user/channel")
        self.recorder.add_package("remote1", "fake/0.1@user/channel", "fake_package_id",
                                  "fake_options", "fake_settings", "fake_requires", False)
        self.recorder.add_recipe("remote2", "fakefake/0.1@user/channel")
        self.recorder.add_package("remote2", "fakefake/0.1@user/channel", "fakefake_package_id1",
                                  "fakefake_options1", "fakefake_settings1", "fakefake_requires1",
                                  False)
        self.recorder.add_package("remote2", "fakefake/0.1@user/channel", "fakefake_package_id2",
                                  "fakefake_options2", "fakefake_settings2", "fakefake_requires2",
                                  False)
        info = self.recorder.get_info()
        expected_result = {
                               "error": False,
                               "results": [
                                   {
                                        "remote": "remote1",
                                        "items": [
                                            {
                                                "recipe": {
                                                    "id": "fake/0.1@user/channel"
                                                },
                                                "packages": [
                                                    {
                                                        "id": "fake_package_id",
                                                        "options": "fake_options",
                                                        "settings": "fake_settings",
                                                        "requires": "fake_requires",
                                                        "outdated": False
                                                    }
                                                ]
                                            }
                                        ]
                                   },
                                   {
                                       "remote": "remote2",
                                       "items": [
                                           {
                                               "recipe": {
                                                   "id": "fakefake/0.1@user/channel"
                                               },
                                               "packages": [
                                                   {
                                                       "id": "fakefake_package_id1",
                                                       "options": "fakefake_options1",
                                                       "settings": "fakefake_settings1",
                                                       "requires": "fakefake_requires1",
                                                       "outdated": False
                                                   },
                                                   {
                                                       "id": "fakefake_package_id2",
                                                       "options": "fakefake_options2",
                                                       "settings": "fakefake_settings2",
                                                       "requires": "fakefake_requires2",
                                                       "outdated": False
                                                   }
                                               ]
                                           }
                                       ]
                                   }
                               ]
        }
        self.assertEqual(expected_result, info)

    def unordered_test(self):
        self.recorder.add_recipe("my_remote1", "fake1/0.1@user/channel")
        self.recorder.add_recipe("my_remote2", "fake2/0.1@user/channel")
        self.recorder.add_recipe("my_remote3", "fake3/0.1@user/channel")
        self.recorder.add_package("my_remote1", "fake1/0.1@user/channel", "fake1_package_id1",
                                  "fake1_options1", "fake1_settings1", "fake1_requires1", False)
        self.recorder.add_package("my_remote2", "fake2/0.1@user/channel", "fake2_package_id1",
                                  "fake2_options1", "fake2_settings1", "fake2_requires1", False)
        self.recorder.add_package("my_remote2", "fake2/0.1@user/channel", "fake2_package_id2",
                                  "fake2_options2", "fake2_settings2", "fake2_requires2", False)
        info = self.recorder.get_info()
        expected_result = {
                            "error": False,
                            "results": [
                                {
                                    "remote": "my_remote1",
                                    "items": [
                                        {
                                            "recipe": {
                                                "id": "fake1/0.1@user/channel"
                                            },
                                            "packages": [
                                                {
                                                    "id": "fake1_package_id1",
                                                    "options": "fake1_options1",
                                                    "settings": "fake1_settings1",
                                                    "requires": "fake1_requires1",
                                                    "outdated": False
                                                }
                                            ]
                                        }
                                    ]
                                },
                                {
                                    "remote": "my_remote2",
                                    "items": [
                                        {
                                            "recipe": {
                                                "id": "fake2/0.1@user/channel"
                                            },
                                            "packages": [
                                                {
                                                    "id": "fake2_package_id1",
                                                    "options": "fake2_options1",
                                                    "settings": "fake2_settings1",
                                                    "requires": "fake2_requires1",
                                                    "outdated": False
                                                },
                                                {
                                                    "id": "fake2_package_id2",
                                                    "options": "fake2_options2",
                                                    "settings": "fake2_settings2",
                                                    "requires": "fake2_requires2",
                                                    "outdated": False
                                                }
                                            ]
                                        }
                                    ]
                                },
                                {
                                    "remote": "my_remote3",
                                    "items": [
                                        {
                                            "recipe": {
                                                "id": "fake3/0.1@user/channel"
                                            },
                                            "packages": []
                                        }
                                    ]
                                }
                            ]
                        }
        self.assertEqual(expected_result, info)

    def without_packages_test(self):
        self.recorder.add_recipe("my_remote1", "fake1/0.1@user/channel", None)
        self.recorder.add_recipe("my_remote2", "fake2/0.1@user/channel", None)
        self.recorder.add_recipe("my_remote3", "fake3/0.1@user/channel", None)
        info = self.recorder.get_info()
        expected_result = {
                            "error": False,
                            "results": [
                                {
                                    "remote": "my_remote1",
                                    "items": [
                                        {
                                            "recipe": {
                                                "id": "fake1/0.1@user/channel"
                                            }
                                        }
                                    ]
                                },
                                {
                                    "remote": "my_remote2",
                                    "items": [
                                        {
                                            "recipe": {
                                                "id": "fake2/0.1@user/channel"
                                            }
                                        }
                                    ]
                                },
                                {
                                    "remote": "my_remote3",
                                    "items": [
                                        {
                                            "recipe": {
                                                "id": "fake3/0.1@user/channel"
                                            }
                                        }
                                    ]
                                }
                            ]
                        }
        self.assertEqual(expected_result, info)
