import textwrap
import unittest

from conans.paths import LAYOUT_PY
from conans.test.utils.tools import TestClient


class LayoutLocalMethodsTest(unittest.TestCase):

    def test_cmake_build_layout(self):
        """cmake layout declared as string, check that build methods work correctly, then
        switch to another layout, like clion with the override"""
        pass
