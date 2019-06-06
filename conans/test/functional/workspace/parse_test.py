# coding=utf-8

import os
import unittest
from collections import namedtuple
from textwrap import dedent

import six

from conans.errors import ConanException
from conans.model.workspace import Workspace
from conans.test.utils.test_files import temp_folder
from conans.util.files import save

MockCache = namedtuple("MockCache", ["cache_folder", ])


class ParseTestSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.default_layout = os.path.join(temp_folder(), "default")
        save(cls.default_layout, "")

    def _parse_ws_file(self, content):
        path = os.path.join(temp_folder(), "filename.yml")
        save(path, content)
        Workspace.create(path, cache=MockCache(cache_folder="."))

    def test_unkonwn_fields_editable(self):
        project = dedent("""
                    editables:
                        HelloB/0.1@lasote/stable:
                            path: B
                            random: something
                    layout: {}
                    workspace_generator: cmake
                    root: HelloB/0.1@lasote/stable
                    """.format(self.default_layout))
        with six.assertRaisesRegex(self, ConanException, "Unrecognized fields 'random' for"
                                                         " editable 'HelloB/0.1@lasote/stable'"):
            self._parse_ws_file(project)

    def test_unknown_fields(self):
        project = dedent("""
            editables:
                HelloB/0.1@lasote/stable:
                    path: B
            layout: {}
            workspace_generator: cmake
            root: HelloB/0.1@lasote/stable
            random: something
            """.format(self.default_layout))
        with six.assertRaisesRegex(self, ConanException, "Unrecognized fields 'random'"):
            self._parse_ws_file(project)

    def test_no_fields(self):
        project = dedent("""
            editables:
                HelloB/0.1@lasote/stable:
            layout: {}
            workspace_generator: cmake
            root: HelloB/0.1@lasote/stable
            """.format(self.default_layout))
        with six.assertRaisesRegex(self, ConanException, "Editable 'HelloB/0.1@lasote/stable'"
                                                         " doesn't define field 'path'"):
            self._parse_ws_file(project)

    def test_no_path_field(self):
        project = dedent("""
            editables:
                HelloB/0.1@lasote/stable:
                    layout: layout
            workspace_generator: cmake
            root: HelloB/0.1@lasote/stable
            """)
        with six.assertRaisesRegex(self, ConanException, "Editable 'HelloB/0.1@lasote/stable'"
                                                         " doesn't define field 'path'"):
            self._parse_ws_file(project)
