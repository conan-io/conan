# coding=utf-8

import os
import textwrap
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


class PythonRequireExportSourcesTest(unittest.TestCase):
    def setUp(self):
        self.pyreq = ConanFileReference.loads("py/req@user/channel")
        conanfile = textwrap.dedent("""\
            import os
            from conans import ConanFile, tools
            
            class PyReq(ConanFile):
                exports_sources = "file.txt"
                
                def source(self):
                    self.output.info(">>>> PyReq::source")
                    self.output.info(">>>> - source_folder: {{}}".format(self.source_folder))
                    self.output.info(self.python_requires)
                    self.output.info(str(self.python_requires['{pyreq_name}'].ref))
            """.format(pyreq_name=self.pyreq.name))

        self.t = TestClient()
        self.t.save({"conanfile.py": conanfile, "file.txt": str(self.pyreq)})
        self.t.run("export . {}".format(self.pyreq))
        self.assertListEqual(['file.txt'], os.listdir(self.t.cache.export_sources(self.pyreq)))

    def test_remote_workflow(self):
        conanfile = textwrap.dedent("""\
            from conans import ConanFile, python_requires
            
            base = python_requires("{pyreq}")
            
            class MyLib(base.PyReq):
                def source(self):
                    # Source method
                    self.output.info(">>>> MyLib::source")
                    super(MyLib, self).source()
                    
                    # Reuse files exported (export_sources) from the python_requires
                    self.output.info("*"*20)
                    self.output.info(self.python_requires)
                    pyreq = self.python_requires['{pyreq_name}']
                    self.output.info(str(pyreq.ref))
                    self.output.info(pyreq.module)
                    self.output.info(pyreq.conanfile)
                    self.output.info(pyreq.export_source_folder)
                    self.output.info("*"*20)
            
            """.format(pyreq=self.pyreq, pyreq_name=self.pyreq.name))

        ref = ConanFileReference.loads("lib/version@user/channel")
        self.t.save({"conanfile.py": conanfile})
        self.t.run("create . {}".format(ref))

        # Check things in 'source' method (source folder is the consuming one)
        source_folder = self.t.cache.source(ref)
        self.assertIn(">>>> PyReq::source", self.t.out)
        self.assertIn(">>>> - source_folder: {}".format(source_folder), self.t.out)

        # Reuse sources from py_req (export_sources)


        print(self.t.out)
