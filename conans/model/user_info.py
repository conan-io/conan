from collections import defaultdict


class UserInfo(object):
    """ Class to be able to assign properties to a dict"""

    def __init__(self):
        self._values_ = {}

    def __getattr__(self, name):
        if name.startswith("_") and name.endswith("_"):
            return super(UserInfo, self).__getattr__(name)

        try:
            return self._values_[name]
        except KeyError:
            raise AttributeError

    def __setattr__(self, name, value):
        if name.startswith("_") and name.endswith("_"):
            return super(UserInfo, self).__setattr__(name, value)
        self._values_[name] = str(value)

    def __repr__(self):
        return str(self._values_)

    @property
    def vars(self):
        return self._values_


class DepsUserInfo(defaultdict):
    def __init__(self):
        super(DepsUserInfo, self).__init__(UserInfo)
