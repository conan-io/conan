#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import os
import shutil
import sys
import tempfile
import unittest
import uuid

import six
import pytest

from conans.client.cmd.export import _replace_scm_data_in_conanfile
from conans.client.graph.python_requires import ConanPythonRequire
from conans.client.loader import parse_conanfile
from conans.test.utils.scm import try_remove_readonly
from conans.util.files import load


class ASTReplacementTest(unittest.TestCase):
    python_requires = ConanPythonRequire(None, None)
    scm_data = {'type': 'git',
                'url': 'this-is-the-url',
                'revision': '42'}

    conanfile = six.u("""{header}
from conans import ConanFile

class LibConan(ConanFile):
    name = "Lib"
    author = "{author}"
    scm = {{"type": "git",
           "url": "auto",
           "revision": "auto"}}
{footer}
    """)

    def run(self, *args, **kwargs):
        self._tmp_folder = tempfile.mkdtemp(suffix='_conans')
        try:
            super(ASTReplacementTest, self).run(*args, **kwargs)
        finally:
            shutil.rmtree(self._tmp_folder, ignore_errors=False, onerror=try_remove_readonly)

    def _get_conanfile(self, header='', author="jgsogo", encoding="ascii", footer=""):
        tmp = os.path.join(self._tmp_folder, str(uuid.uuid4()))
        with codecs.open(tmp, 'w', encoding=encoding) as f:
            f.write(self.conanfile.format(header=header, author=author, footer=footer))
        return tmp

    def _check_result(self, conanfile):
        content = load(conanfile)

        self.assertEqual(content.count(self.scm_data['url']), 1)
        self.assertEqual(content.count(self.scm_data['revision']), 1)
        self.assertIn(self.scm_data['url'], content)
        self.assertIn(self.scm_data['revision'], content)

        try:
            # Check it is loadable by Conan machinery
            _, conanfile = parse_conanfile(conanfile, python_requires=self.python_requires,
                                           generator_manager=None)
        except Exception as e:
            self.fail("Invalid conanfile: {}".format(e))
        else:
            self.assertEqual(conanfile.scm, self.scm_data)

    def test_base(self):
        conanfile = self._get_conanfile()
        _replace_scm_data_in_conanfile(conanfile, self.scm_data)
        self._check_result(conanfile)

    @pytest.mark.skipif(not six.PY3, reason="Works only in Py3 (assumes utf-8 for source files)")
    def test_author_non_ascii(self):
        conanfile = self._get_conanfile(author=six.u("¡ÑÁí!"), encoding='utf-8')
        _replace_scm_data_in_conanfile(conanfile, self.scm_data)
        self._check_result(conanfile)

    def test_shebang_utf8(self):
        header = "#!/usr/bin/env python2\n# -*- coding: utf-8 -*-"
        conanfile = self._get_conanfile(author=six.u("¡Ñandú!"), header=header, encoding='utf-8')
        _replace_scm_data_in_conanfile(conanfile, self.scm_data)
        self._check_result(conanfile)

    def test_shebang_ascii(self):
        header = "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-"
        conanfile = self._get_conanfile(author="jgsogo", header=header, encoding='ascii')
        _replace_scm_data_in_conanfile(conanfile, self.scm_data)
        self._check_result(conanfile)

    def test_shebang_several(self):
        header = "#!/usr/bin/env python2\n# -*- coding: utf-8 -*-\n# -*- coding: utf-8 -*-"
        conanfile = self._get_conanfile(author=six.u("¡Ñandú!"), header=header, encoding='utf-8')
        _replace_scm_data_in_conanfile(conanfile, self.scm_data)
        self._check_result(conanfile)

    def test_multiline_statement(self):
        """ Statement with several lines below the scm attribute """
        statement = "\n    long_list = 'a', 'b', 'c' \\\n        'd', 'e'"
        conanfile = self._get_conanfile(footer=statement)
        _replace_scm_data_in_conanfile(conanfile, self.scm_data)
        self._check_result(conanfile)

    # Add comments below the SCM
    def test_comment_file_level(self):
        comment = "# This is a comment, file level"
        conanfile = self._get_conanfile(footer=comment)
        self.assertIn(comment, load(conanfile))
        _replace_scm_data_in_conanfile(conanfile, self.scm_data)
        self._check_result(conanfile)
        self.assertIn(comment, load(conanfile))

    def test_comment_class_level(self):
        comment = "    # This is a comment, file level"
        conanfile = self._get_conanfile(footer=comment)
        self.assertIn(comment, load(conanfile))
        _replace_scm_data_in_conanfile(conanfile, self.scm_data)
        self._check_result(conanfile)
        self.assertIn(comment, load(conanfile))

    def test_two_comments(self):
        comment = "    # line1\n    # line2"
        conanfile = self._get_conanfile(footer=comment)
        self.assertIn(comment, load(conanfile))
        _replace_scm_data_in_conanfile(conanfile, self.scm_data)
        self._check_result(conanfile)
        self.assertIn(comment, load(conanfile))

    @pytest.mark.skipif(sys.version_info.major == 3 and sys.version_info.minor >= 9,
                        reason="no py39")
    def test_multiline_comment(self):
        comment = '    """\n    line1\n    line2\n    """'
        conanfile = self._get_conanfile(footer=comment)
        self.assertIn(comment, load(conanfile))
        _replace_scm_data_in_conanfile(conanfile, self.scm_data)
        self._check_result(conanfile)
        # FIXME: We lost the multiline comment
        # self.assertIn(comment, load(conanfile))

    # Something below the comment
    def test_comment_and_attribute(self):
        comment = '    # line1\n    url=23'
        conanfile = self._get_conanfile(footer=comment)
        self.assertIn(comment, load(conanfile))
        _replace_scm_data_in_conanfile(conanfile, self.scm_data)
        self._check_result(conanfile)
        self.assertIn(comment, load(conanfile))

    @pytest.mark.skipif(sys.version_info.major == 3 and sys.version_info.minor >= 9,
                        reason="no py39")
    def test_multiline_comment_and_attribute(self):
        comment = '    """\n    line1\n    line2\n    """\n    url=23'
        conanfile = self._get_conanfile(footer=comment)
        self.assertIn(comment, load(conanfile))
        _replace_scm_data_in_conanfile(conanfile, self.scm_data)
        self._check_result(conanfile)
        # FIXME: We lost the multiline comment
        self.assertIn("    url=23", load(conanfile))
        # self.assertIn(comment, load(conanfile))
