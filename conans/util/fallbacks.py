# coding=utf-8

import warnings


def default_output(output, fn_name=None, tools=None):
    if output is None:
        fn_str = " to function '{}'".format(fn_name) if fn_name else ''
        warnings.warn("Provide the output argument explicitly{}".format(fn_str))

        return tools.output

    return output


def default_requester(requester, fn_name=None, tools=None):
    if requester is None:
        fn_str = " to function '{}'".format(fn_name) if fn_name else ''
        warnings.warn("Provide the requester argument explicitly{}".format(fn_str))

        return tools.requester

    return requester
