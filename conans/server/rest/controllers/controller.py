'''
Generic controller.
Abstact class dor define attach_to method
'''
from abc import ABCMeta, abstractmethod


class Controller(object):
    __metaclass__ = ABCMeta

    def __init__(self, route):
        self.route = route

    @abstractmethod
    def attach_to(self, app):
        raise NotImplemented()
