import os
import unittest
import re
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient, TestRequester, TestServer
from conans.util.files import save
from six.moves.urllib.parse import quote_plus, unquote, urlparse


class PutPropertiesTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}

    def create_empty_property_file_test(self):

        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        client.save(files)
        client.run("export . lasote/stable")
        props_file = client.cache.artifacts_properties_path
        self.assertTrue(os.path.exists(props_file))

    def put_properties_test(self):
        wanted_vars = {"key0": "value",
                       "key1": "with space",
                       #"key2": "with/slash",  # FIXME: Not supported in conan-server
                       "key3": "with.dot",
                       "key4": "with;semicolon",
                       "key5": "with~virgul",
                       "key6": "with#hash"
                       }

        class RequesterCheckArtifactProperties(TestRequester):
            def put(self_requester, url, **kwargs):
                # Check headers
                for name, value in wanted_vars.items():
                    value1 = kwargs["headers"][name]
                    self.assertEqual(value1, value)

                # Check matrix params
                mp = re.match(r"^[^;\s]+;(?P<matrix_params>[^/]+)/.*", url).group("matrix_params")
                values = [it.split("=") for it in mp.split(';')]
                values = {key: unquote(value) for (key, value) in values}
                for name, value in wanted_vars.items():
                    value1 = values[name]
                    self.assertEqual(value1, value)

                return super(RequesterCheckArtifactProperties, self_requester).put(url, **kwargs)

        self.client = TestClient(requester_class=RequesterCheckArtifactProperties,
                                 servers=self.servers,
                                 users={"default": [("lasote", "mypass")]})
        _create_property_files(self.client, wanted_vars)

        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.client.run("upload Hello0/0.1@lasote/stable -c")


def _create_property_files(client, values):
    lines = ["#Some comment", " #Some comments"]
    for name, value in values.items():
        lines.append("%s=%s" % (name, value))
    save(client.cache.artifacts_properties_path, "\n".join(lines))
