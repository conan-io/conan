from conans.client.downloaders.utils import hash_url


class TestHashUrl(object):

    def test_user_download(self):
        url = 'https://domain.url/file'
        assert hash_url(url, None, user_download=True) == hash_url(url, None, user_download=False)
        url = 'https://domain.url/file?qs=23'
        assert hash_url(url, None, user_download=True) != hash_url(url, None, user_download=False)

    def test_checksum(self):
        url = 'https://domain.url/file'
        assert hash_url(url, None, False) != hash_url(url, 'checksum', False)

    def test_url(self):
        assert hash_url('http://netloc', None, False) != hash_url('https://netloc', None, False)
        assert hash_url('http://netloc', None, False) != hash_url('http://netloc1', None, False)
        assert hash_url('http://netloc/p1', None, False) != hash_url('http://netloc/p2', None, False)
