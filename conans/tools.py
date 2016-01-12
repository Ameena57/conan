""" ConanFile user tools, as download, etc
"""
import sys
import os
from urllib import FancyURLopener
import urllib2
from conans.errors import ConanException
from conans.util.files import _generic_algorithm_sum


def human_size(size_bytes):
    """
    format a size in bytes into a 'human' file size, e.g. bytes, KB, MB, GB, TB, PB
    Note that bytes/KB will be reported in whole numbers but MB and above will have greater precision
    e.g. 1 byte, 43 bytes, 443 KB, 4.3 MB, 4.43 GB, etc
    """
    if size_bytes == 1:
        return "1 byte"

    suffixes_table = [('bytes', 0), ('KB', 0), ('MB', 1), ('GB', 2), ('TB', 2), ('PB', 2)]

    num = float(size_bytes)
    for suffix, precision in suffixes_table:
        if num < 1024.0:
            break
        num /= 1024.0

    if precision == 0:
        formatted_size = "%d" % num
    else:
        formatted_size = str(round(num, ndigits=precision))

    return "%s %s" % (formatted_size, suffix)


def update_progress(progress, total_size):
    '''prints a progress bar, with percentages, and auto-cr so always printed in same line
    @param progress: percentage, float
    @param total_size: file total size in Mb
    '''
    bar_length = 40
    status = ""
    if progress < 0:
        progress = 0
        status = "Halt...\r\n"
    if progress >= 1:
        progress = 1
        status = "Done...\r\n"
    block = int(round(bar_length * progress))
    text = "\rPercent: [{0}] {1:.1f}% of {2} {3}".format("#" * block +
                                                               "-" * (bar_length - block),
                                                               progress * 100, human_size(total_size), status)
    sys.stdout.write(text)
    sys.stdout.flush()


def unzip(filename, destination="."):
    if ".tar.gz" in filename or ".tgz" in filename:
        return untargz(filename, destination)
    import zipfile
    full_path = os.path.normpath(os.path.join(os.getcwd(), destination))
    with zipfile.ZipFile(filename, "r") as z:
        uncompress_size = sum((file_.file_size for file_ in z.infolist()))
        print "Unzipping %s, this can take a while" % (human_size(uncompress_size))
        extracted_size = 0
        for file_ in z.infolist():
            extracted_size += file_.file_size
            print "Unzipping %.0f %%\r" % (extracted_size * 100.0 / uncompress_size),
            try:
                if len(file_.filename) + len(full_path) > 200:
                    raise ValueError("Filename too long")
                z.extract(file_, full_path)
            except Exception as e:
                print "Error extract %s\n%s" % (file_.filename, str(e))


def untargz(filename, destination="."):
    import tarfile
    with tarfile.TarFile.open(filename, 'r:gz') as tarredgzippedFile:
        tarredgzippedFile.extractall(destination)


def get(url):
    """ high level downloader + unziper + delete temporary zip
    """
    filename = os.path.basename(url)
    download(url, filename)
    unzip(filename)
    os.unlink(filename)


AGENT = 'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) '\
        'Chrome/41.0.2228.0 Safari/537.36'


def fetch_sourceforge_url(url):
    opener = urllib2.build_opener()
    opener.addheaders = [('User-agent', AGENT)]
    new_url = ""
    try:
        response = opener.open(url)
        html = response.read()
        good_url_pos_init = html.find("http://downloads.sourceforge.net")
        good_url_pos_fin = html[good_url_pos_init:].find("\"") + good_url_pos_init
        new_url = html[good_url_pos_init:good_url_pos_fin]
    finally:
        if not new_url:
            raise ConanException("File not found: %s" % url)
    return new_url


def download(url, filename):
    def dl_progress_callback_cmd(count, block_size, total_size):
        update_progress(min(count * block_size, total_size) / float(total_size), total_size)

    # Some websites blocks urllib (maybe for block scripts or crawl)
    class MyOpener(FancyURLopener):
        version = (AGENT)

    if "sourceforge.net" in url:
        url = fetch_sourceforge_url(url)

    try:
        MyOpener().retrieve(url, filename=filename, reporthook=dl_progress_callback_cmd)
    except:
        retrieve(url, filename=filename, reporthook=dl_progress_callback_cmd)

def replace_in_file(file_path, search, replace):
    with open(file_path, 'r') as content_file:
        content = content_file.read()
        content = content.replace(search, replace)
    with open(file_path, 'wb') as handle:
        handle.write(content)


def check_with_algorithm_sum(algorithm_name, file_path, signature):

    real_signature = _generic_algorithm_sum(file_path, algorithm_name)
    if real_signature != signature:
        raise ConanException("%s signature failed for '%s' file."
                             " Computed signature: %s" % (algorithm_name,
                                                          os.path.basename(file_path),
                                                          real_signature))


def check_sha1(file_path, signature):
    check_with_algorithm_sum("sha1", file_path, signature)


def check_md5(file_path, signature):
    check_with_algorithm_sum("md5", file_path, signature)


def check_sha256(file_path, signature):
    check_with_algorithm_sum("sha256", file_path, signature)
