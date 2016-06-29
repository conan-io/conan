import unittest
from conans.test.tools import TestClient
import os


class GeneratorsTest(unittest.TestCase):

    def test_base(self):
        base = '''
[generators]
cmake
gcc
qbs
qmake
txt
visual_studio
xcode
ycm
    '''
        files = {"conanfile.txt": base}
        client = TestClient()
        client.save(files)
        client.run("install --build")
        self.assertEqual(sorted(['conanfile.txt', 'conaninfo.txt', 'conanbuildinfo.cmake',
                                 'conanbuildinfo.gcc', 'conanbuildinfo.qbs', 'conanbuildinfo.pri',
                                 'conanbuildinfo.txt', 'conanbuildinfo.props',
                                 'conanbuildinfo.xcconfig', '.ycm_extra_conf.py']),
                         sorted(os.listdir(client.current_folder)))
