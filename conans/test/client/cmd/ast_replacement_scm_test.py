#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import unittest
import tempfile
import shutil
import uuid
import codecs
import six

from conans.util.files import load
from conans.test.utils.tools import handleRemoveReadonly
from conans.client.cmd.export import _replace_scm_data_in_conanfile


class ASTReplacementTest(unittest.TestCase):
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
    """)

    def run(self, *args, **kwargs):
        self._tmp_folder = tempfile.mkdtemp(suffix='_conans')
        try:
            super(ASTReplacementTest, self).run(*args, **kwargs)
        finally:
            shutil.rmtree(self._tmp_folder, ignore_errors=False, onerror=handleRemoveReadonly)

    def _get_conanfile(self, header='', author="jgsogo", encoding="ascii"):
        tmp = os.path.join(self._tmp_folder, str(uuid.uuid4()))
        with codecs.open(tmp, 'w', encoding=encoding) as f:
            f.write(self.conanfile.format(header=header, author=author))
        return tmp

    def _check_result(self, conanfile):
        content = load(conanfile)

        self.assertEqual(content.count(self.scm_data['url']), 1)
        self.assertEqual(content.count(self.scm_data['revision']), 1)
        self.assertIn(self.scm_data['url'], content)
        self.assertIn(self.scm_data['revision'], content)

    def test_base(self):
        conanfile = self._get_conanfile()
        _replace_scm_data_in_conanfile(conanfile, self.scm_data)
        self._check_result(conanfile)

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