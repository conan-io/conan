"""
Server's configuration variables
"""

from conans.util.env_reader import get_env
from datetime import timedelta
import os
import random
import string
from conans.errors import ConanException
from conans.util.files import save, mkdir
from six.moves.configparser import ConfigParser, NoSectionError
from conans.paths import SimplePaths
from conans.server.store.disk_adapter import DiskAdapter
from conans.server.store.file_manager import FileManager
from conans.util.log import logger
from conans.server.conf.default_server_conf import default_server_conf

MIN_CLIENT_COMPATIBLE_VERSION = '0.8.0'


class ConanServerConfigParser(ConfigParser):
    """ defines the configuration of the server. It can load
    values from environment variables or from file.
    Environment variables have PREDECENDENCE over file values
    """
    def __init__(self, base_folder, storage_folder=None, environment=os.environ):
        ConfigParser.__init__(self)
        self.conan_folder = os.path.join(base_folder, '.conan_server')
        self.config_filename = os.path.join(self.conan_folder, 'server.conf')
        self._loaded = False
        self.env_config = {"updown_secret": get_env("CONAN_UPDOWN_SECRET", None, environment),
                           "store_adapter": get_env("CONAN_STORE_ADAPTER", None, environment),
                           "authorize_timeout": get_env("CONAN_AUTHORIZE_TIMEOUT", None, environment),
                           "disk_storage_path": get_env("CONAN_STORAGE_PATH", storage_folder, environment),
                           "jwt_secret": get_env("CONAN_JWT_SECRET", None, environment),
                           "jwt_expire_minutes": get_env("CONAN_JWT_EXPIRE_MINUTES", None, environment),
                           "write_permissions": [],
                           "read_permissions": [],
                           "ssl_enabled": get_env("CONAN_SSL_ENABLED", None, environment),
                           "port": get_env("CONAN_SERVER_PORT", None, environment),
                           "public_port": get_env("CONAN_SERVER_PUBLIC_PORT", None, environment),
                           "host_name": get_env("CONAN_HOST_NAME", None, environment),
                           # "user:pass,user2:pass2"
                           "users": get_env("CONAN_SERVER_USERS", None, environment)}

    def _get_file_conf(self, section, varname=None):
        """Gets the section from config file or raises an exception"""
        try:
            if not os.path.exists(self.config_filename):
                jwt_random_secret = ''.join(random.choice(string.ascii_letters) for _ in range(24))
                updown_random_secret = ''.join(random.choice(string.ascii_letters) for _ in range(24))
                server_conf = default_server_conf.format(jwt_secret=jwt_random_secret,
                                                         updown_secret=updown_random_secret)
                save(self.config_filename, server_conf)

            if not self._loaded:
                self._loaded = True
                self.read(self.config_filename)

            if varname:
                section = dict(self.items(section))
                return section[varname]
            else:
                return self.items(section)
        except NoSectionError as exc:
            raise ConanException("No section '%s' found" % section)
        except Exception as exc:
            logger.debug(exc)
            raise ConanException("Invalid configuration, "
                                 "missing %s: %s" % (section, varname))

    @property
    def ssl_enabled(self):
        if self.env_config["ssl_enabled"]:
            return self.env_config["ssl_enabled"] == "true" or \
                   self.env_config["ssl_enabled"] == "1"
        else:
            return self._get_file_conf("server", "ssl_enabled").lower() == "true" or \
                   self._get_file_conf("server", "ssl_enabled").lower() == "1"

    @property
    def port(self):
        if self.env_config["port"]:
            return int(self.env_config["port"])
        else:
            return int(self._get_file_conf("server", "port"))

    @property
    def public_port(self):
        if self.env_config["public_port"]:
            return int(self.env_config["public_port"])
        elif self._get_file_conf("server", "public_port"):
            return int(self._get_file_conf("server", "public_port"))
        else:
            return self.port

    @property
    def host_name(self):
        return self._get_conf_server_string("host_name")

    @property
    def public_url(self):
        protocol = "https" if self.ssl_enabled else "http"
        port = ":%s" % self.public_port if self.public_port != 80 else ""
        return "%s://%s%s/v1" % (protocol, self.host_name, port)

    @property
    def disk_storage_path(self):
        """If adapter is disk, means the directory for storage"""
        if self.env_config["disk_storage_path"]:
            ret = self.env_config["disk_storage_path"]
        else:
            try:
                ret = os.path.expanduser(self._get_file_conf("server", "disk_storage_path"))
            except ConanException:
                # If storage_path is not defined in file, use the current dir
                # So tests use test folder instead of user/.conan_server
                ret = os.path.dirname(self.config_filename)
        ret = os.path.normpath(ret)  # Convert to O.S paths
        mkdir(ret)
        return ret

    @property
    def read_permissions(self):
        if self.env_config["read_permissions"]:
            return self.env_config["read_permissions"]
        else:
            return self._get_file_conf("read_permissions")

    @property
    def write_permissions(self):
        if self.env_config["write_permissions"]:
            return self.env_config["write_permissions"]
        else:
            return self._get_file_conf("write_permissions")

    @property
    def users(self):
        def validate_pass_encoding(password):
            try:
                password.encode('ascii')
            except (UnicodeDecodeError, UnicodeEncodeError):
                raise ConanException("Password contains invalid characters. Only ASCII encoding is supported")
            return password

        if self.env_config["users"]:
            pairs = self.env_config["users"].split(",")
            return {pair.split(":")[0]: validate_pass_encoding(pair.split(":")[1]) for pair in pairs}
        else:
            tmp = dict(self._get_file_conf("users"))
            tmp = {key: validate_pass_encoding(value) for key, value in tmp.items()}
            return tmp

    @property
    def jwt_secret(self):
        tmp = self._get_conf_server_string("jwt_secret")
        if not tmp:
            raise ConanException("'jwt_secret' setting is needed. Please, write a value "
                                 "in server.conf or set CONAN_JWT_SECRET env value.")
        return tmp

    @property
    def updown_secret(self):
        tmp = self._get_conf_server_string("updown_secret")
        if not tmp:
            raise ConanException("'updown_secret' setting is needed. Please, write a value "
                                 "in server.conf or set CONAN_UPDOWN_SECRET env value.")
        return self._get_conf_server_string("updown_secret")

    @property
    def store_adapter(self):
        return self._get_conf_server_string("store_adapter")

    def _get_conf_server_string(self, keyname):
        if self.env_config[keyname]:
            return self.env_config[keyname]
        else:
            return self._get_file_conf("server", keyname)

    @property
    def authorize_timeout(self):
        if self.env_config["authorize_timeout"]:
            return timedelta(seconds=int(self.env_config["authorize_timeout"]))
        else:
            tmp = self._get_file_conf("server", "authorize_timeout")
            return timedelta(seconds=int(tmp))

    @property
    def jwt_expire_time(self):
        if self.env_config["jwt_expire_minutes"]:
            return timedelta(minutes=int(self.env_config["jwt_expire_minutes"]))
        else:
            tmp = float(self._get_file_conf("server", "jwt_expire_minutes"))
            return timedelta(minutes=tmp)


def get_file_manager(config, public_url=None, updown_auth_manager=None):
    store_adapter = config.store_adapter
    if store_adapter == "disk":
        public_url = public_url or config.public_url
        disk_controller_url = "%s/%s" % (public_url, "files")
        if not updown_auth_manager:
            raise Exception("Updown auth manager needed for disk controller (not s3)")
        adapter = DiskAdapter(disk_controller_url, config.disk_storage_path, updown_auth_manager)
        paths = SimplePaths(config.disk_storage_path)
    else:
        # Want to develop new adapter? create a subclass of 
        # conans.server.store.file_manager.StorageAdapter and implement the abstract methods
        raise Exception("Store adapter not implemented! Change 'store_adapter' "
                        "variable in server.conf file to one of the available options: 'disk' ")
    return FileManager(paths, adapter)
