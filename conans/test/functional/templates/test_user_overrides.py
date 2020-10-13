import os
import unittest

from conans.assets.templates import SEARCH_TABLE_HTML, INFO_GRAPH_DOT, INFO_GRAPH_HTML
from conans.client.tools import save
from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient, GenConanfile


class UserOverridesTemplatesTestCase(unittest.TestCase):
    lib_ref = ConanFileReference.loads("lib/version")
    app_ref = ConanFileReference.loads("app/version")

    @classmethod
    def setUpClass(cls):
        cls.t = TestClient()
        cls.t.save({'lib.py': GenConanfile().with_setting("os"),
                    'app.py': GenConanfile().with_setting("os").with_require(cls.lib_ref)})
        cls.t.run("create lib.py {}@ -s os=Windows".format(cls.lib_ref))
        cls.t.run("create lib.py {}@ -s os=Linux".format(cls.lib_ref))
        cls.t.run("create app.py {}@ -s os=Windows".format(cls.app_ref))
        cls.t.run("create app.py {}@ -s os=Linux".format(cls.app_ref))

    def test_table_html(self):
        table_template_path = os.path.join(self.t.cache_folder, 'templates', SEARCH_TABLE_HTML)
        save(table_template_path, content='{{ base_template_path }}')
        self.t.run("search {}@ --table=output.html".format(self.lib_ref))
        content = self.t.load("output.html")
        self.assertEqual(os.path.join(self.t.cache_folder, 'templates', 'output'), content)

    def test_graph_html(self):
        table_template_path = os.path.join(self.t.cache_folder, 'templates', INFO_GRAPH_HTML)
        save(table_template_path, content='{{ base_template_path }}')
        self.t.run("info {}@ --graph=output.html".format(self.app_ref))
        content = self.t.load("output.html")
        self.assertEqual(os.path.join(self.t.cache_folder, 'templates', 'output'), content)

    def test_graph_dot(self):
        table_template_path = os.path.join(self.t.cache_folder, 'templates', INFO_GRAPH_DOT)
        save(table_template_path, content='{{ base_template_path }}')
        self.t.run("info {}@ --graph=output.dot".format(self.app_ref))
        content = self.t.load("output.dot")
        self.assertEqual(os.path.join(self.t.cache_folder, 'templates', 'output'), content)
