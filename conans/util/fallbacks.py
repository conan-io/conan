# coding=utf-8

import warnings


def default_output(output, fn_name=None):
    if output is None:
        fn_str = " to function '{}'".format(fn_name) if fn_name else ''
        warnings.warn("Provide the output argument explicitly{}".format(fn_str))

        from conans.tools import _global_output
        return _global_output

    return output


def default_requester(requester, fn_name=None):
    if requester is None:
        fn_str = " to function '{}'".format(fn_name) if fn_name else ''
        warnings.warn("Provide the requester argument explicitly{}".format(fn_str))

        from conans.tools import _global_requester
        return _global_requester

    return requester
