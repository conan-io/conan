# coding=utf-8

import requests
import unittest
import re


class ToolsDocsCongruencyTest(unittest.TestCase):

    re_identifier = "[a-zA-Z_]\w*"

    def _get_published_tools(self, branch):
        url = "https://raw.githubusercontent.com/conan-io/docs/{}/reference/tools.rst".format(branch)
        r = requests.get(url=url)
        content = r.content
        tools_list = {it.group(1) for it in re.finditer(r"tools\.({})".format(self.re_identifier), str(content))}
        for it in tools_list:
            assert it.isidentifier(), it
        return tools_list

    def test_tools(self):
        tools_list = self._get_published_tools(branch='develop')

        import conans.tools as conans_tools
        for it in tools_list:
            self.assertTrue(hasattr(conans_tools, it), msg="Failed for 'tools.{}'".format(it))
