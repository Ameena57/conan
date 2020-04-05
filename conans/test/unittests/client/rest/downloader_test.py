import re
import tempfile
import unittest

from conans.client.rest.file_downloader import FileDownloader
from conans.errors import ConanException
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import load


class _ConfigMock:
    def __init__(self):
        self.retry = 0
        self.retry_wait = 0


class MockResponse(object):
    def __init__(self, data, headers, status_code=200):
        self.data = data
        self.ok = True
        self.status_code = status_code
        self.headers = headers.copy()
        self.headers.update({key.lower(): value for key, value in headers.items()})

    def iter_content(self, size):
        for i in range(0, len(self.data), size):
            yield self.data[i:i + size]

    def close(self):
        pass


class MockRequester(object):
    retry = 0
    retry_wait = 0

    def __init__(self, data, chunk_size=None):
        self._data = data
        self._chunk_size = chunk_size if chunk_size is not None else len(data)

    def get(self, *_args, **kwargs):
        start = 0
        headers = kwargs.get("headers") or {}
        transfer_range = headers.get("range", "")
        match = re.match(r"bytes=([0-9]+)-", transfer_range)
        status = 200
        headers = {"Content-Length": len(self._data), "Accept-Ranges": "bytes"}
        if match:
            start = int(match.groups()[0])
            status = 206
            headers.update({"Content-Length": len(self._data) - start,
                            "Content-Range": "bytes {}-{}/{}".format(start, len(self._data) - 1,
                                                               len(self._data))})
            assert start <= len(self._data)

        response = MockResponse(self._data[start:start + self._chunk_size], status_code=status,
                                headers=headers)
        return response


class DownloaderUnitTest(unittest.TestCase):
    def setUp(self):
        self.target = tempfile.mktemp()
        self.out = TestBufferConanOutput()

    def test_download_file_ok(self):
        expected_content = b"some data"
        requester = MockRequester(expected_content)
        downloader = FileDownloader(requester=requester, output=self.out, verify=None,
                                    config=_ConfigMock())
        downloader.download("fake_url", file_path=self.target)
        actual_content = load(self.target, binary=True)
        self.assertEqual(expected_content, actual_content)

    def test_download_file_interrupted(self):
        expected_content = b"some data"
        requester = MockRequester(expected_content, chunk_size=4)
        downloader = FileDownloader(requester=requester, output=self.out, verify=None,
                                    config=_ConfigMock())
        downloader.download("fake_url", file_path=self.target)
        actual_content = load(self.target, binary=True)
        self.assertEqual(expected_content, actual_content)

    def test_fail_download_file_no_progress(self):
        expected_content = b"some data"
        requester = MockRequester(expected_content, chunk_size=0)
        downloader = FileDownloader(requester=requester, output=self.out, verify=None,
                                    config=_ConfigMock())
        with self.assertRaisesRegexp(ConanException, r"Download failed"):
            downloader.download("fake_url", file_path=self.target)
