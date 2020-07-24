# coding=utf-8

import warnings
import sys

from conans.client.output import colorama_initialize, ConanOutput
from conans.errors import ConanException


def default_output(output, fn_name=None):
    if output is None:
        fn_str = " to function '{}'".format(fn_name) if fn_name else ''
        warnings.warn("Provide the output argument explicitly{}".format(fn_str))
        out = ConanOutput(sys.stdout, sys.stderr, colorama_initialize())
        return out

    return output


def default_requester(requester, fn_name=None):
    if requester is None:
        fn_str = " to function '{}'".format(fn_name) if fn_name else ''
        warnings.warn("Provide the requester argument explicitly{}".format(fn_str))

        # Generate a default requester is more complex ...
        # ConanRequester(self.config, http_requester)
        raise ConanException("Ops! There is no default requester.")

    return requester
