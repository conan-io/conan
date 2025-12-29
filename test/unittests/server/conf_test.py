import os
import pytest
from datetime import timedelta

from conan.errors import ConanException
from conans.server.conf import ConanServerConfigParser
from conan.test.utils.test_files import temp_folder
from conan.internal.util.config_parser import TextINIParse
from conan.internal.util.files import save

fileconfig = '''
[server]
jwt_secret: mysecret
jwt_expire_minutes: 121
disk_storage_path: %s
ssl_enabled: true
port: 9220
host_name: localhost
public_port: 12345


[write_permissions]
openssl/2.0.1@lasote/testing: pepe

[read_permissions]
*/*@*/*: *
openssl/2.0.1@lasote/testing: pepe

[users]
lasote: defaultpass
pepe: pepepass
'''


class TestServerConf:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.file_path = temp_folder()
        server_conf = os.path.join(self.file_path, '.conan_server/server.conf')
        self.storage_path = os.path.join(self.file_path, "storage")
        save(server_conf, fileconfig % self.storage_path)
        self.environ = {}

    def test_unexpected_section(self):
        text = """
[one]
text=value
[two]
other=var
[three]
var
[moon]
var=walker
"""

        with pytest.raises(ConanException):
            TextINIParse(text, ["one", "two", "three"])
        conf = TextINIParse(text)
        assert conf.one == "text=value"
        assert conf.two == "other=var"
        assert conf.three == "var"
        assert conf.moon == "var=walker"

        # IF an old config file is readed but the section is in the list, just return it empty
        text = """
[one]
text=value
        """
        conf = TextINIParse(text)
        assert conf.two == ""

    def test_values(self):
        config = ConanServerConfigParser(self.file_path, environment=self.environ)
        assert config.jwt_secret == "mysecret"
        assert config.jwt_expire_time == timedelta(minutes=121)
        assert config.disk_storage_path == self.storage_path
        assert config.ssl_enabled
        assert config.port == 9220
        assert config.write_permissions == [("openssl/2.0.1@lasote/testing", "pepe")]
        assert config.read_permissions == [("*/*@*/*", "*"),
                                                    ("openssl/2.0.1@lasote/testing", "pepe")]
        assert config.users == {"lasote": "defaultpass", "pepe": "pepepass"}
        assert config.host_name == "localhost"
        assert config.public_port == 12345
        assert config.public_url == "https://localhost:12345/v2"

        # Now check with environments
        tmp_storage = temp_folder()
        self.environ["CONAN_STORAGE_PATH"] = tmp_storage
        self.environ["CONAN_JWT_SECRET"] = "newkey"
        self.environ["CONAN_JWT_EXPIRE_MINUTES"] = "123"
        self.environ["CONAN_SSL_ENABLED"] = "False"
        self.environ["CONAN_SERVER_PORT"] = "1233"
        self.environ["CONAN_SERVER_USERS"] = "lasote:lasotepass,pepe2:pepepass2"
        self.environ["CONAN_HOST_NAME"] = "remotehost"
        self.environ["CONAN_SERVER_PUBLIC_PORT"] = "33333"

        config = ConanServerConfigParser(self.file_path, environment=self.environ)
        assert config.jwt_secret ==  "newkey"
        assert config.jwt_expire_time == timedelta(minutes=123)
        assert config.disk_storage_path == tmp_storage
        assert not config.ssl_enabled
        assert config.port == 1233
        assert config.write_permissions == [("openssl/2.0.1@lasote/testing", "pepe")]
        assert config.read_permissions == [("*/*@*/*", "*"),
                                                    ("openssl/2.0.1@lasote/testing", "pepe")]
        assert config.users == {"lasote": "lasotepass", "pepe2": "pepepass2"}
        assert config.host_name == "remotehost"
        assert config.public_port == 33333
        assert config.public_url == "http://remotehost:33333/v2"
