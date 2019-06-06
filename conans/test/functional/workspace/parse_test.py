# coding=utf-8

import os
import unittest
from textwrap import dedent

import six

from conans.errors import ConanException
from conans.model.workspace import Workspace
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


class ParseTestSuite(unittest.TestCase):

    def _parse_ws_file(self, content):
        path = os.path.join(temp_folder(), "filename.yml")
        save(path, content)
        Workspace.create(path, cache=None)

    def test_root_not_editable(self):
        project = dedent("""
                    workspace_generator: cmake
                    root: Hellob/0.1@lasote/stable
                    """)
        with six.assertRaisesRegex(self, ConanException,
                                   "Root Hellob/0.1@lasote/stable is not defined as editable"):
            self._parse_ws_file(project)

    def test_unkonwn_fields_editable(self):
        project = dedent("""
                    editables:
                        HelloB/0.1@lasote/stable:
                            path: B
                            random: something
                    workspace_generator: cmake
                    root: HelloB/0.1@lasote/stable
                    """)
        with six.assertRaisesRegex(self, ConanException, "Unrecognized fields 'random' for"
                                                         " editable 'HelloB/0.1@lasote/stable'"):
            self._parse_ws_file(project)

    def test_unknown_fields(self):
        project = dedent("""
            editables:
                HelloB/0.1@lasote/stable:
                    path: B
            workspace_generator: cmake
            root: HelloB/0.1@lasote/stable
            random: something
            """)
        with six.assertRaisesRegex(self, ConanException, "Unrecognized fields 'random'"):
            self._parse_ws_file(project)

    def test_no_fields(self):
        project = dedent("""
            editables:
                HelloB/0.1@lasote/stable:
            workspace_generator: cmake
            root: HelloB/0.1@lasote/stable
            """)
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
