import getpass
import os
import platform
import sys

from conans.errors import ConanException


def is_terminal(stream):
    return hasattr(stream, "isatty") and stream.isatty()


def color_enabled(stream):
    """
    NO_COLOR: No colors and no colorama
    CLICOLOR: When 1, colors if is_terminal
    CLICOLOR_FORCE: When 1, always colors (except if NO_COLOR)
    """
    if os.getenv("NO_COLOR") == "1":
        return False
    elif os.getenv("CLICOLOR_FORCE") == "1" or (os.getenv("CLICOLOR", "1") != "0"
                                                and is_terminal(stream)):
        return True
    else:
        return False


def init_colorama(stream):
    import colorama
    if not color_enabled(stream):
        if os.getenv("NO_COLOR") != "1":
            colorama.init(strip=True)
        return False
    else:
        # convert=False => Not convert ANSI color bytes to win32 color bytes
        # strip=True => Remove ANSI color bytes from code
        # wrap=False => Do not mock sys.stderr not sys.stdout, because crashes subprocess.popen
        import colorama
        if colorama.ansitowin32.winterm:
            colorama.init(strip=True, convert=False)
        else:
            # wrap=False
            colorama.init(wrap=False)
        return True


class UserInput(object):
    """Class to interact with the user, used to show messages and ask for information"""

    def __init__(self, non_interactive):
        """
        Params:
            ins: input stream
            out: ConanOutput, should have "write" method
        """
        self._ins = sys.stdin
        # FIXME: circular include, move "color_enabled" function to better location
        from conans.cli.output import ConanOutput
        self._out = ConanOutput()
        self._interactive = not non_interactive

    def _raise_if_non_interactive(self):
        if not self._interactive:
            raise ConanException("Conan interactive mode disabled")

    def raw_input(self):
        self._raise_if_non_interactive()
        return input()

    def request_login(self, remote_name, username=None):
        """Request user to input their name and password
        :param username If username is specified it only request password"""

        if not username:
            if self._interactive:
                self._out.write("Remote '%s' username: " % remote_name)
            username = self._get_env_username(remote_name)
            if not username:
                self._raise_if_non_interactive()
                username = self.get_username(remote_name)

        if self._interactive:
            self._out.write('Please enter a password for "%s" account: ' % username)
        try:
            pwd = self._get_env_password(remote_name)
            if not pwd:
                self._raise_if_non_interactive()
                pwd = self.get_password(remote_name)
        except ConanException:
            raise
        except Exception as e:
            raise ConanException('Cancelled pass %s' % e)
        return username, pwd

    def get_username(self, remote_name):
        """Overridable for testing purpose"""
        return self.raw_input()

    def get_password(self, remote_name):
        """Overridable for testing purpose"""
        self._raise_if_non_interactive()
        return getpass.getpass("")

    def request_string(self, msg, default_value=None):
        """Request user to input a msg
        :param msg Name of the msg
        """
        self._raise_if_non_interactive()

        if default_value:
            self._out.write('%s (%s): ' % (msg, default_value))
        else:
            self._out.write('%s: ' % msg)
        s = self._ins.readline().replace("\n", "")
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
                self._out.error("%s is not a valid answer" % s)
        return ret

    def _get_env_password(self, remote_name):
        """
        Try CONAN_PASSWORD_REMOTE_NAME or CONAN_PASSWORD or return None
        """
        remote_name = remote_name.replace("-", "_").upper()
        var_name = "CONAN_PASSWORD_%s" % remote_name
        ret = os.getenv(var_name, None) or os.getenv("CONAN_PASSWORD", None)
        if ret:
            self._out.info("Got password '******' from environment")
        return ret

    def _get_env_username(self, remote_name):
        """
        Try CONAN_LOGIN_USERNAME_REMOTE_NAME or CONAN_LOGIN_USERNAME or return None
        """
        remote_name = remote_name.replace("-", "_").upper()
        var_name = "CONAN_LOGIN_USERNAME_%s" % remote_name
        ret = os.getenv(var_name, None) or os.getenv("CONAN_LOGIN_USERNAME", None)

        if ret:
            self._out.info("Got username '%s' from environment" % ret)
        return ret
