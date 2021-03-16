import os
import platform
import textwrap
import unittest

from conans.client.tools.intel import intel_installation_path
from conans.errors import ConanException
from conans.test.utils.tools import TestClient


class BaseIntelTestCase(unittest.TestCase):
    def setUp(self):
        try:
            installation_path = intel_installation_path(self.version, self.arch)
            if not os.path.isdir(installation_path):
                raise unittest.SkipTest("Intel C++ compiler is required")
        except ConanException:
            raise unittest.SkipTest("Intel C++ compiler is required")

        self.t = TestClient()

    @property
    def version(self):
        return '19.1'

    @property
    def arch(self):
        return "x86_64"

    @property
    def settings(self):
        the_os = {'Darwin': 'Macos'}.get(platform.system(), platform.system())
        vars = [('compiler', 'intel'),
                ('compiler.version', self.version),
                ('build_type', 'Release'),
                ('arch', self.arch),
                ('os', the_os)]
        if platform.system() == "Windows":
            vars.append(('compiler.base', 'Visual Studio'))
            vars.append(('compiler.base.version', '15'))
            vars.append(('compiler.base.runtime', 'MD'))
        else:
            vars.append(('compiler.base', 'gcc'))
            vars.append(('compiler.base.version', '10'))
            vars.append(('compiler.base.libcxx', 'libstdc++'))
        return vars

    @property
    def profile(self):
        template = textwrap.dedent("""
            include(default)
            [settings]
            {settings}
            """)
        settings = '\n'.join(["%s = %s" % (s[0], s[1]) for s in self.settings])
        return template.format(settings=settings)
