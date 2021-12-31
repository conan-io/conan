import os
import textwrap


from conans.test.utils.tools import TestClient


class TestSettingsLoad:
    def test_invalid_settings(self):
        client = TestClient()
        client.save({os.path.join(client.cache_folder, 'settings.yml'): """your buggy file""",
                     "conanfile.txt": ""})
        client.run("install .", assert_error=True)
        assert "ERROR: Invalid settings.yml format" in client.out

    def test_invalid_yaml(self):
        client = TestClient()
        client.save({os.path.join(client.cache_folder, 'settings.yml'):
                     textwrap.dedent("""
                        Almost:
                            - a
                            - valid
                          yaml
                     """),
                     "conanfile.txt": ""})
        client.run("install .", assert_error=True)
        assert "ERROR: Invalid settings.yml format: while parsing a block mapping" in client.out
