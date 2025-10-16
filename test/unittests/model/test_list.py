from conan.api.model import PackagesList


def test_package_list_only_recipes():
    pl = PackagesList()
    pl.recipes = {
        "foobar/0.1.0": {'revisions':
                             {'85eb0587a3c12b90216c72070e9eef3e':
                                  {'timestamp': 1740151190.975,
                                   'packages': {'c29f32beda3c361f536ba35aae5e876faf970169':
                                       {'revisions': {
                                           '9a0569c04839fff6a6e8f40e10434bc6':
                                               {'timestamp': 1742417567.684486}},
                                           'info': {}}}}}},
        "qux/0.2.1": {'revisions':
                          {'71c3c11b98a6f2ae11f0f391f5e62e2b':
                               {'timestamp': 1740151186.976, 'packages':
                                   {'13be611585c95453f1cbbd053cea04b3e64470ca':
                                        {'revisions': {'5c7e0c0788cd4d89249ad251f0868787':
                                                           {'timestamp': 1740152032.884}},
                                         'info':
                                             {'settings':
                                                  {'arch': 'x86_64',
                                                   'build_type': 'Release',
                                                   'compiler': 'gcc',
                                                   'compiler.cppstd': '17',
                                                   'compiler.libcxx': 'libstdc++11',
                                                   'compiler.version': '11', 'os': 'Linux'},
                                              'options': {'fPIC': 'True', 'shared': 'False'}}},
                                    '30652ea35b512fa3fe0f4dcd39ad217e4e60bd01':
                                        {'revisions': {'8f363f1d95ad766ac400e1f1f5406599':
                                                           {'timestamp': 1741861639.2198145}},
                                         'info': {}},
                                    'fc491156b442836722612d1aa8a8c57e406447b6':
                                        {'revisions': {'62e9e2659596c97cd1dd313d4394e947':
                                                           {'timestamp': 1740151900.394}},
                                         'info': {
                                             'settings':
                                                 {'arch': 'x86_64', 'build_type': 'Release',
                                                  'compiler': 'gcc', 'compiler.cppstd': '17',
                                                  'compiler.libcxx': 'libstdc++11',
                                                  'compiler.version': '11', 'os': 'Linux'},
                                             'options': {'shared': 'True'}}}}}}}
    }
    pl.only_recipes()
    assert pl.recipes == {'foobar/0.1.0': {
        'revisions': {'85eb0587a3c12b90216c72070e9eef3e': {'timestamp': 1740151190.975}}},
                       'qux/0.2.1': {'revisions': {
                           '71c3c11b98a6f2ae11f0f391f5e62e2b': {'timestamp': 1740151186.976}}}}
