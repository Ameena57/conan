import calendar
import datetime
import re
import time

from dateutil import parser

from conans.errors import ConanException


def from_timestamp_to_iso8601(timestamp):
    # Used exclusively by conan_server to return the date in iso format (same as artifactory)
    return "%sZ" % datetime.datetime.utcfromtimestamp(int(timestamp)).isoformat()


def from_iso8601_to_datetime(iso_str):
    return parser.isoparse(iso_str)


def from_iso8601_to_timestamp(iso_str):
    datetime_time = from_iso8601_to_datetime(iso_str)
    return datetime_time.timestamp()


def iso8601_to_str(iso_str):
    dt = from_iso8601_to_datetime(iso_str)
    return dt.strftime('%Y-%m-%d %H:%M:%S UTC')


def timestamp_now():
    # seconds since epoch 0, easy to store, in UTC
    return calendar.timegm(time.gmtime())


def revision_timestamp_now():
    return time.time()


def timestamp_to_str(timestamp):
    assert timestamp is not None
    return datetime.datetime.utcfromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S UTC')


def timedelta_from_text(interval):
    match = re.search(r"(\d+)([smhdw])", interval)
    try:
        value, unit = match.group(1), match.group(2)
        name = {'s': 'seconds',
                'm': 'minutes',
                'h': 'hours',
                'd': 'days',
                'w': 'weeks'}[unit]
        return datetime.timedelta(**{name: float(value)})
    except Exception:
        raise ConanException("Incorrect time interval definition: %s" % interval)
