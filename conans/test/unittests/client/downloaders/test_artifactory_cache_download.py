from conans.client.downloaders.artifactory_cache_downloader import ArtifactoryCacheDownloader

from errors import ConanException


class FakeFileDownloader(object):
    rt_domain = 'https://jfrog.rt'

    def __init__(self, rt_found):
        self.calls = []
        self._rt_found = rt_found

    def download(self, url, **kwargs):
        self.calls.append(url)
        if not self._rt_found and url.startswith(self.rt_domain):
            raise ConanException("File '{url}' not found".format(url=url))


class TestArtifactoryCacheDownload(object):

    def test_rt_file_exist(self):
        fake_downloader = FakeFileDownloader(True)
        rt_downloader = ArtifactoryCacheDownloader('https://jfrog.rt', fake_downloader)
        rt_downloader.download('https://domain.url/filename', file_path='filesystem_path')
        assert len(fake_downloader.calls) == 1
        assert fake_downloader.calls[0].startswith('https://jfrog.rt')

    def test_rt_file_not_found(self):
        fake_downloader = FakeFileDownloader(False)
        rt_downloader = ArtifactoryCacheDownloader('https://jfrog.rt', fake_downloader)
        rt_downloader.download('https://domain.url/filename', file_path='filesystem_path')
        assert len(fake_downloader.calls) == 2
        assert fake_downloader.calls[0].startswith('https://jfrog.rt')
        assert fake_downloader.calls[1] == 'https://domain.url/filename'
