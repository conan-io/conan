import os
import re
import unittest

from six.moves.urllib.parse import unquote

from conans import MATRIX_PARAMS
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestRequester, TestServer
from conans.util.files import save


class PutPropertiesTest(unittest.TestCase):

    def test_create_empty_property_file(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("Hello", "0.1")})
        client.run("export . lasote/stable")
        props_file = client.cache.artifacts_properties_path
        self.assertTrue(os.path.exists(props_file))

    def test_put_properties(self):
        test_server = TestServer()
        servers = {"default": test_server}

        wanted_vars = {"key0": "value",
                       "key1": "with space",
                       "key2": "with/slash",
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
                self.assertNotIn(';', url)
                mp = re.match(r"^[^;\s]+;(?P<matrix_params>[^/]+)/.*", url)
                self.assertFalse(mp)

                return super(RequesterCheckArtifactProperties, self_requester).put(url, **kwargs)

        client = TestClient(requester_class=RequesterCheckArtifactProperties,
                            servers=servers, users={"default": [("lasote", "mypass")]})
        _create_property_files(client, wanted_vars)

        client.save({"conanfile.py": GenConanfile("Hello0", "0.1")})
        client.run("export . lasote/stable")
        client.run("upload Hello0/0.1@lasote/stable -c")

    def test_matrix_params(self):
        test_server = TestServer(server_capabilities=[MATRIX_PARAMS, ])
        servers = {"default": test_server}

        wanted_vars = {"key0": "value",
                       "key1": "with space",
                       "key2": "with/slash",
                       "key3": "with.dot",
                       "key4": "with;semicolon",
                       "key5": "with~virgul",
                       "key6": "with#hash"
                       }

        class RequesterCheckArtifactProperties(TestRequester):
            def put(self_requester, url, **kwargs):
                # Check headers
                self.assertListEqual(list(kwargs["headers"].keys()),
                                     ["X-Checksum-Sha1", "User-Agent"])

                # Check matrix params
                m = re.match(r"^[^;\s]+;(?P<matrix_params>[^/]+)/.*", url)
                mp = m.group("matrix_params")
                values = [it.split("=") for it in mp.split(';')]
                values = {key: unquote(value) for (key, value) in values}
                for name, value in wanted_vars.items():
                    value1 = values[name]
                    self.assertEqual(value1, value)

                slice_start, slice_end = m.span(1)
                url = url[: slice_start-1] + url[slice_end:]  # matrix params are not implemented for conan-server
                return super(RequesterCheckArtifactProperties, self_requester).put(url, **kwargs)

        client = TestClient(requester_class=RequesterCheckArtifactProperties,
                            servers=servers, users={"default": [("lasote", "mypass")]})
        _create_property_files(client, wanted_vars)

        client.save({"conanfile.py": GenConanfile("Hello0", "0.1")})
        client.run("export . lasote/stable")
        client.run("upload Hello0/0.1@lasote/stable -c")


def _create_property_files(client, values):
    lines = ["#Some comment", " #Some comments"]
    for name, value in values.items():
        lines.append("%s=%s" % (name, value))
    save(client.cache.artifacts_properties_path, "\n".join(lines))
