import os
import unittest

import pytest

from conans.assets.templates import SEARCH_TABLE_HTML, INFO_GRAPH_DOT, INFO_GRAPH_HTML
from conans.test.utils.tools import TestClient, GenConanfile
from conans.util.files import save


class UserOverridesTemplatesTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.t = TestClient()
        cls.t.save({'lib.py': GenConanfile("lib", "0.1").with_setting("os"),
                    'app.py': GenConanfile("app", "0.1").with_setting("os").with_require("lib/0.1")})
        cls.t.run("create lib.py -s os=Windows")
        cls.t.run("create lib.py -s os=Linux")
        cls.t.run("create app.py -s os=Windows")
        cls.t.run("create app.py -s os=Linux")

    @pytest.mark.xfail(reason="Tests using the Search command are temporarely disabled")
    def test_table_html(self):
        table_template_path = os.path.join(self.t.cache_folder, 'templates', SEARCH_TABLE_HTML)
        save(table_template_path, content='{{ base_template_path }}')
        self.t.run("search {}@ --table=output.html".format(self.lib_ref))
        content = self.t.load("output.html")
        self.assertEqual(os.path.join(self.t.cache_folder, 'templates', 'output'), content)

    def test_graph_html(self):
        table_template_path = os.path.join(self.t.cache_folder, 'templates', INFO_GRAPH_HTML)
        save(table_template_path, content='{{ base_template_path }}')
        self.t.run("graph info --requires=app/0.1 --format=html")
        content = self.t.stdout
        self.assertEqual(os.path.join(self.t.cache_folder, 'templates'), content)

    def test_graph_dot(self):
        table_template_path = os.path.join(self.t.cache_folder, 'templates', INFO_GRAPH_DOT)
        save(table_template_path, content='{{ base_template_path }}')
        self.t.run("graph info --requires=app/0.1 --format=dot")
        content = self.t.stdout
        self.assertEqual(os.path.join(self.t.cache_folder, 'templates'), content)
