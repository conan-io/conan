import sys
from conans.client.output import ConanOutput
from conans.model.username import Username
from conans.errors import InvalidNameException, ConanException
import getpass
from six.moves import input as raw_input


class UserIO(object):
    """Class to interact with the user, used to show messages and ask for information"""
    def __init__(self, ins=sys.stdin, out=None):
        '''
        Params:
            ins: input stream
            out: ConanOutput, should have "write" method
        '''
        self._ins = ins
        if not out:
            out = ConanOutput(sys.stdout)
        self.out = out

    def request_login(self, remote_name, username=None):
        """Request user to input their name and password
        :param username If username is specified it only request password"""
        user_input = ''
        while not username:
            try:
                self.out.write("Remote '%s' username: " % remote_name)
                user_input = self.get_username(remote_name)
                username = Username(user_input)
            except InvalidNameException:
                self.out.error('%s is not a valid username' % user_input)

        self.out.write('Please enter a password for "%s" account: ' % username)
        try:
            pwd = self.get_password(remote_name)
        except Exception as e:
            raise ConanException('Cancelled pass %s' % e)
        return username, pwd

    def get_username(self, remote_name):
        """Overridable for testing purpose"""
        return raw_input()

    def get_password(self, remote_name):
        """Overridable for testing purpose"""
        return getpass.getpass("")

    def request_string(self, msg, default_value=None):
        """Request user to input a msg
        :param msg Name of the msg
        """
        if default_value:
            self.out.input_text('%s (%s): ' % (msg, default_value))
        else:
            self.out.input_text('%s: ' % msg)
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
                self.out.error("%s is not a valid answer" % s)
        return ret
