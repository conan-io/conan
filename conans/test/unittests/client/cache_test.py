from conans.client.cache.cache import ClientCache
from conans.test.utils.test_files import temp_folder
from conans.util.env import environment_update


class TestCache:

    def test_localdb_uses_encryption(self):
        tmp_dir = temp_folder()
        with environment_update({"CONAN_LOGIN_ENCRYPTION_KEY": "key"}):
            cache = ClientCache(tmp_dir)
            localdb = cache.localdb
            assert localdb.encryption_key == "key"
