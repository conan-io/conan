import unittest

from conans.search.binary_html_table import RowResult, Headers, Results


class RowResultTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = {'id': '1234',
                'outdated': True,
                'extra': 'never used',
                'settings': {'os': 'Windows'},
                'options': {'opt.key1': 23},
                'requires': ['pkg1/version:1234', 'pkg2/version@user/channel:12345']}
        cls.row_result = RowResult("remote", "name/version@user/testing", data)

    def test_basic(self):
        self.assertEqual(self.row_result.remote, "remote")
        self.assertEqual(self.row_result.reference, "name/version@user/testing")
        self.assertEqual(self.row_result.recipe, "name/version@user/testing")
        self.assertEqual(self.row_result.package_id, "1234")
        self.assertEqual(self.row_result.outdated, True)

    def test_row(self):
        headers = Headers(settings=['os', 'os.api'], options=['opt.key1'], requires=True,
                          keys=['remote', 'reference', 'outdated', 'package_id'])
        row = list(self.row_result.row(headers))
        self.assertEqual(row, ['remote', 'name/version@user/testing', True, '1234',  # Keys
                               'Windows', None,  # Settings
                               23,  # Options
                               'pkg1/version, pkg2/version@user/channel'  # Requires
                               ])


class HeadersTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        settings = ['build_type', 'os', 'other', 'compiler', 'compiler.version',
                    'compiler.libcxx', 'os.api', ]
        options = ['opt.key1', 'opt2']
        requires = True
        keys = ['remote', 'reference', 'outdated', 'package_id']
        cls.headers = Headers(settings, options, requires, keys)

    def test_settings_ordering(self):
        self.assertEqual(self.headers.settings, ['os', 'os.api', 'compiler', 'compiler.libcxx',
                                                 'compiler.version', 'build_type', 'other'])

    def test_1row(self):
        row = self.headers.row(n_rows=1)
        # Order: keys, settings, options and requires
        self.assertEqual(row, [
            'remote', 'reference', 'outdated', 'package_id',
            'os', 'os.api', 'compiler', 'compiler.libcxx', 'compiler.version', 'build_type', 'other',
            'opt.key1', 'opt2',
            'requires'])

    def test_2row(self):
        row = self.headers.row(n_rows=2)
        self.assertEqual(row, [
            # Keys
            ('remote', ['']), ('reference', ['']), ('outdated', ['']), ('package_id', ['']),
            # Settings
            ('os', ['', 'api']), ('compiler', ['', 'libcxx', 'version']), ('build_type', ['']),
            ('other', ['']),
            # Options
            ('options', ['opt.key1', 'opt2']),
            # Requires
            ('requires', [''])
        ])


class ResultsTestCase(unittest.TestCase):
    def test_gather_data(self):
        # Data returned by the API protocol
        json = [
            {
                'remote': 'remote1',
                'items': [{
                    'recipe': {'id': 'name/version@user/channel'},
                    'packages': [
                        {
                            'settings': {'os': 'Windows', 'os.api': 23},
                            'options': {'opt.key1': 'option_value'},
                            'requires': []
                        },
                        {
                            'settings': {'os': 'Windows', 'compiler': 'VS'},
                            'options': {},
                            'requires': ['pkgA/vv:1234', 'pkgB/vv@user/testing:12345']
                        }
                    ]
                }]
            },
            {
                'remote': 'remote2',
                'items': [{'packages': []}]
            }
        ]

        results = Results(json)
        self.assertListEqual(sorted(results.settings), sorted(['os.api', 'os', 'compiler']))
        self.assertListEqual(results.options, ['opt.key1'])
        self.assertEqual(results.requires, True)
        self.assertListEqual(sorted(results.remotes), sorted(['remote1', 'remote2']))
