from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestRequester


class RequesterClass(TestRequester):

    def get(self, url, headers=None, **kwargs):
        print(f"URL: {url}-HEADERS: {headers}")
        return super(RequesterClass, self).get(url, headers=headers, **kwargs)


def test_request_info_headers():
    c = TestClient(requester_class=RequesterClass, default_server_user=True)
    conanfile = GenConanfile("pkg", "0.1").with_settings('os', 'arch', 'compiler') \
                                          .with_shared_option(False)
    c.save({'conanfile.py': conanfile})
    c.run("export .")
    c.run("install --requires=pkg/0.1 -s arch=x86_64", assert_error=True)
    assert "'Conan-PkgID-Options': 'shared=False'" in c.out
    assert "'Conan-PkgID-Settings': 'arch=x86_64;" in c.out

