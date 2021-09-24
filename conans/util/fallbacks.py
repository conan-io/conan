# coding=utf-8

import warnings


def default_requester(requester, fn_name=None):
    if requester is None:
        fn_str = " to function '{}'".format(fn_name) if fn_name else ''
        warnings.warning("Provide the requester argument explicitly{}".format(fn_str))

        from conans.tools import _global_requester
        return _global_requester

    return requester
