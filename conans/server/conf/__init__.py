"""
Server's configuration variables
"""

import os
import random
import string
from datetime import timedelta

import six
from six.moves.configparser import ConfigParser, NoSectionError

from conans.client import tools
from conans.errors import ConanException
from conans.paths import conan_expand_user
from conans.server.conf.default_server_conf import default_server_conf
from conans.server.store.disk_adapter import ServerDiskAdapter
from conans.server.store.server_store import ServerStore
from conans.util.env_reader import get_env
from conans.util.files import mkdir, save
from conans.util.log import logger

MIN_CLIENT_COMPATIBLE_VERSION = '0.25.0'


class ConanServerConfigParser(ConfigParser):
    """ defines the configuration of the server. It can load
    values from environment variables or from file.
    Environment variables have PRECEDENCE over file values
    """

    def __init__(self, base_folder, environment=None, is_custom_path=False):
        environment = environment or os.environ

        ConfigParser.__init__(self)
        environment = environment or os.environ
        self.optionxform = str  # This line keeps the case of the key, important for users case
        if is_custom_path:
            self.conan_folder = base_folder
        else:
            self.conan_folder = os.path.join(base_folder, '.conan_server')
        self.config_filename = os.path.join(self.conan_folder, 'server.conf')
        self._loaded = False
        self.env_config = {"updown_secret": get_env("CONAN_UPDOWN_SECRET", None, environment),
                           "authorize_timeout": get_env("CONAN_AUTHORIZE_TIMEOUT", None, environment),
                           "disk_storage_path": get_env("CONAN_STORAGE_PATH", None, environment),
                           "jwt_secret": get_env("CONAN_JWT_SECRET", None, environment),
                           "jwt_expire_minutes": get_env("CONAN_JWT_EXPIRE_MINUTES", None, environment),
                           "write_permissions": [],
                           "read_permissions": [],
                           "ssl_enabled": get_env("CONAN_SSL_ENABLED", None, environment),
                           "port": get_env("CONAN_SERVER_PORT", None, environment),
                           "public_port": get_env("CONAN_SERVER_PUBLIC_PORT", None, environment),
                           "host_name": get_env("CONAN_HOST_NAME", None, environment),
                           "custom_authenticator": get_env("CONAN_CUSTOM_AUTHENTICATOR", None, environment),
                           "custom_authorizer": get_env("CONAN_CUSTOM_AUTHORIZER", None, environment),
                           # "user:pass,user2:pass2"
                           "users": get_env("CONAN_SERVER_USERS", None, environment)}

    def _get_file_conf(self, section, varname=None):
        """ Gets the section or variable from config file.
        If the queried element is not found an exception is raised.
        """
        try:
            if not os.path.exists(self.config_filename):
                jwt_random_secret = ''.join(random.choice(string.ascii_letters) for _ in range(24))
                updown_random_secret = ''.join(random.choice(string.ascii_letters) for _ in range(24))
                server_conf = default_server_conf.format(jwt_secret=jwt_random_secret,
                                                         updown_secret=updown_random_secret)
                save(self.config_filename, server_conf)

            if not self._loaded:
                self._loaded = True
                # To avoid encoding problems we use our tools.load
                if six.PY3:
                    self.read_string(tools.load(self.config_filename))
                else:
                    self.read(self.config_filename)

            if varname:
                section = dict(self.items(section))
                return section[varname]
            else:
                return self.items(section)
        except NoSectionError:
            raise ConanException("No section '%s' found" % section)
        except Exception as exc:
            logger.debug(exc)
            raise ConanException("Invalid configuration, "
                                 "missing %s: %s" % (section, varname))

    @property
    def ssl_enabled(self):
        try:
            ssl_enabled = self._get_conf_server_string("ssl_enabled").lower()
            return ssl_enabled == "true" or ssl_enabled == "1"
        except ConanException:
            return None

    @property
    def port(self):
        return int(self._get_conf_server_string("port"))

    @property
    def public_port(self):
        try:
            return int(self._get_conf_server_string("public_port"))
        except ConanException:
            return self.port

    @property
    def host_name(self):
        try:
            return self._get_conf_server_string("host_name")
        except ConanException:
            return None

    @property
    def public_url(self):
        host_name = self.host_name
        ssl_enabled = self.ssl_enabled
        protocol_version = "v1"
        if host_name is None and ssl_enabled is None:
            # No hostname and ssl config means that the transfer and the
            # logical endpoint are the same and a relative URL is sufficient
            return protocol_version
        elif host_name is None or ssl_enabled is None:
            raise ConanException("'host_name' and 'ssl_enable' have to be defined together.")
        else:
            protocol = "https" if ssl_enabled else "http"
            port = ":%s" % self.public_port if self.public_port != 80 else ""
            return "%s://%s%s/%s" % (protocol, host_name, port, protocol_version)

    @property
    def disk_storage_path(self):
        """If adapter is disk, means the directory for storage"""
        try:
            disk_path = self._get_conf_server_string("disk_storage_path")
            if disk_path.startswith("."):
                disk_path = os.path.join(os.path.dirname(self.config_filename), disk_path)
                disk_path = os.path.abspath(disk_path)
            ret = conan_expand_user(disk_path)
        except ConanException:
            # If storage_path is not defined, use the current dir
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
    def custom_authenticator(self):
        try:
            return self._get_conf_server_string("custom_authenticator")
        except ConanException:
            return None

    @property
    def custom_authorizer(self):
        try:
            return self._get_conf_server_string("custom_authorizer")
        except ConanException:
            return None

    @property
    def users(self):
        def validate_pass_encoding(password):
            try:
                password.encode('ascii')
            except (UnicodeDecodeError, UnicodeEncodeError):
                raise ConanException("Password contains invalid characters. "
                                     "Only ASCII encoding is supported")
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
        try:
            return self._get_conf_server_string("jwt_secret")
        except ConanException:
            raise ConanException("'jwt_secret' setting is needed. Please, write a value "
                                 "in server.conf or set CONAN_JWT_SECRET env value.")

    @property
    def updown_secret(self):
        try:
            return self._get_conf_server_string("updown_secret")
        except ConanException:
            raise ConanException("'updown_secret' setting is needed. Please, write a value "
                                 "in server.conf or set CONAN_UPDOWN_SECRET env value.")

    def _get_conf_server_string(self, keyname):
        """ Gets the value of a server config value either from the environment
        or the config file. Values from the environment have priority. If the
        value is not defined or empty an exception is raised.
        """
        if self.env_config[keyname]:
            return self.env_config[keyname]

        value = self._get_file_conf("server", keyname)
        if value == "":
            raise ConanException("no value for 'server.%s' is defined in the config file" % keyname)
        return value

    @property
    def authorize_timeout(self):
        return timedelta(seconds=int(self._get_conf_server_string("authorize_timeout")))

    @property
    def jwt_expire_time(self):
        return timedelta(minutes=float(self._get_conf_server_string("jwt_expire_minutes")))


def get_server_store(disk_storage_path, public_url, updown_auth_manager):
    disk_controller_url = "%s/%s" % (public_url, "files")
    if not updown_auth_manager:
        raise Exception("Updown auth manager needed for disk controller (not s3)")
    adapter = ServerDiskAdapter(disk_controller_url, disk_storage_path, updown_auth_manager)
    return ServerStore(adapter)
