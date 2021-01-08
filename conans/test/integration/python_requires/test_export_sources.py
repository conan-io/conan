# coding=utf-8

import os
import textwrap
import unittest
from jinja2 import Template

from conans.model.ref import ConanFileReference
from parameterized import parameterized
from conans.test.utils.tools import TestClient


class PythonRequireExportSourcesTest(unittest.TestCase):
    def setUp(self):
        self.pyreq = ConanFileReference.loads("py/req@user/channel")
        conanfile = textwrap.dedent("""\
            import os
            from conans import ConanFile, tools
            
            class PyReq(ConanFile):
                exports_sources = "exports_sources.txt", "more_exports_sources.txt"
                exports = "exports.txt", "more_exports.txt"
                
                def source(self, is_empty):
                    self.output.info(">>>> PyReq::source")
                    self.output.info(">>>> - source_folder: {{}}".format(self.source_folder))
                    file_list = sorted(os.listdir(self.source_folder))
                    self.output.info(">>>> - source list: {{}}".format(file_list))
                    if is_empty:
                        assert not file_list, "No files expected, found {{}}".format(file_list)
                    else:
                        assert file_list, "Files expected, but it is empty"
                        assert sorted(["more_exports_sources.txt", "more_exports.txt"]) == file_list
            """.format(pyreq_name=self.pyreq.name))

        self.t = TestClient()
        self.t.save({"conanfile.py": conanfile,
                     "exports_sources.txt": "exports_sources: {}".format(str(self.pyreq)),
                     "exports.txt": "exports: {}".format(str(self.pyreq))})
        self.t.run("export . {}".format(self.pyreq))
        package_layout = self.t.cache.package_layout(self.pyreq)
        self.assertListEqual(['exports_sources.txt'],
                             os.listdir(package_layout.export_sources()))
        self.assertListEqual(sorted(['exports.txt', 'conanfile.py', 'conanmanifest.txt']),
                             sorted(os.listdir(package_layout.export())))

    @parameterized.expand([(False, ), (True, )])
    def test_locate_pyreq_folders(self, empty_exports):
        conanfile = Template(textwrap.dedent("""\
            from conans import ConanFile, python_requires
            
            base = python_requires("{{ pyreq }}")
            
            class MyLib(base.PyReq):
                {% if empty %}
                exports_sources = None
                exports = None
                {% endif %}
                
                def source(self):
                    super(MyLib, self).source(is_empty={{ empty }})

                    self.output.info(">>>> MyLib::source")
                    pyreq = self.python_requires['{{ pyreq.name }}']
                    self.output.info(" - pyreq::ref: {{{}}}".format(str(pyreq.ref)))
                    self.output.info(" - pyreq::exports_sources: {{{}}}".format(pyreq.exports_sources_folder))
                    self.output.info(" - pyreq::exports: {{{}}}".format(pyreq.exports_folder))
            
            """))
        content = conanfile.render(pyreq=self.pyreq, empty=empty_exports)

        ref = ConanFileReference.loads("lib/version@user/channel")
        self.t.save({"conanfile.py": content}, clean_first=True)
        if not empty_exports:
            # Write some files, these will be exported because they match patterns in pyreq
            self.t.save({"more_exports.txt": "...",
                         "more_exports_sources.txt": "..."})
        self.t.run("create . {}".format(ref))

        # Check things written in 'source' method (source folder executed in consumer context)
        source_folder = self.t.cache.package_layout(ref).source()
        self.assertIn(">>>> PyReq::source", self.t.out)
        self.assertIn(">>>> - source_folder: {}".format(source_folder), self.t.out)
        if not empty_exports:
            self.assertIn(">>>> - source list: ['more_exports.txt', 'more_exports_sources.txt']",
                          self.t.out)
        else:
            self.assertIn(">>>> - source list: []", self.t.out)

        # Access to sources from pyreq, check folders match
        pyreq_layout = self.t.cache.package_layout(self.pyreq)
        self.assertIn(" - pyreq::ref: {}".format(self.pyreq), self.t.out)
        self.assertIn(" - pyreq::exports_sources: %s" % pyreq_layout.export_sources(), self.t.out)
        self.assertIn(" - pyreq::exports: %s" % pyreq_layout.export(), self.t.out)
