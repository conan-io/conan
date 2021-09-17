import getpass
import os
import sys

from conans.client.output import ConanOutput
from conans.errors import ConanException


class UserIO(object):
    """Class to interact with the user, used to show messages and ask for information"""

    def __init__(self):
        self.out = ConanOutput()
        self._input_disabled = False

    def raw_input(self):
        return input()

    def disable_input(self):
        self._input_disabled = True

    def get_pass(self):
        return getpass.getpass("")

    def request_login(self, remote_name, username=None):
        """Request user to input their name and password
        :param username If username is specified it only request password"""

        if not username:
            self.out.write("Remote '%s' username: " % remote_name)
            username = self.get_username(remote_name)

        self.out.write('Please enter a password for "%s" account: ' % username)
        try:
            pwd = self.get_password(remote_name)
        except ConanException:
            raise
        except Exception as e:
            raise ConanException('Cancelled pass %s' % e)
        return username, pwd

    def get_username(self, remote_name):
        """Overridable for testing purpose"""
        return self._get_env_username(remote_name) or self.raw_input()

    def get_password(self, remote_name):
        """Overridable for testing purpose"""
        return self._get_env_password(remote_name) or self.get_pass()

    def request_string(self, msg, default_value=None):
        """Request user to input a msg
        :param msg Name of the msg
        """
        if self._input_disabled:
            raise ConanException("Conan interactive mode disabled")


        if default_value:
            self.out.input_text('%s (%s): ' % (msg, default_value))
        else:
            self.out.input_text('%s: ' % msg)
        s = sys.stdin.readline().replace("\n", "")
        if default_value is not None and s == '':
            return default_value
        return s

    def request_boolean(self, msg, default_option=None):
        """Request user to input a boolean"""
        ret = None
        while ret is None:
            if default_option is True:
                s = self.request_string("%s (YES/no)" % msg)
            elif default_option is False:
                s = self.request_string("%s (NO/yes)" % msg)
            else:
                s = self.request_string("%s (yes/no)" % msg)
            if default_option is not None and s == '':
                return default_option
            if s.lower() in ['yes', 'y']:
                ret = True
            elif s.lower() in ['no', 'n']:
                ret = False
            else:
                self.out.error("%s is not a valid answer" % s)
        return ret

    def _get_env_password(self, remote_name):
        """
        Try CONAN_PASSWORD_REMOTE_NAME or CONAN_PASSWORD or return None
        """
        remote_name = remote_name.replace("-", "_").upper()
        var_name = "CONAN_PASSWORD_%s" % remote_name
        ret = os.getenv(var_name, None) or os.getenv("CONAN_PASSWORD", None)
        if ret:
            self.out.info("Got password '******' from environment")
        return ret

    def _get_env_username(self, remote_name):
        """
        Try CONAN_LOGIN_USERNAME_REMOTE_NAME or CONAN_LOGIN_USERNAME or return None
        """
        remote_name = remote_name.replace("-", "_").upper()
        var_name = "CONAN_LOGIN_USERNAME_%s" % remote_name
        ret = os.getenv(var_name, None) or os.getenv("CONAN_LOGIN_USERNAME", None)

        if ret:
            self.out.info("Got username '%s' from environment" % ret)
        return ret
