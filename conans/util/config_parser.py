import re
from conans.errors import ConanException
from conans.model.ref import ConanFileReference


def get_bool_from_text_value(value):
    """ to be deprecated
    It has issues, as accepting into the registry whatever=value, as False, withoug
    complaining
    """
    return (value == "1" or value.lower() == "yes" or value.lower() == "y" or
            value.lower() == "true") if value else True


def get_bool_from_text(value):
    value = value.lower()
    if value in ["1", "yes", "y", "true"]:
        return True
    if value in ["0", "no", "n", "false"]:
        return False
    raise ConanException("Unrecognized boolean value '%s'" % value)


class ConfigParser(object):
    """ util class to load a file with sections as [section1]
    checking the values of those sections, and returns each section
    as parser.section
    Currently used in ConanInfo and ConanFileTextLoader
    """
    def __init__(self, text, allowed_fields=None, parse_lines=False, raise_unexpected_field=True):
        self._sections = {}
        self._allowed_fields = allowed_fields or []
        pattern = re.compile("^\[([a-z_]{2,50})\]")
        current_lines = None
        for line in text.splitlines():
            line = line.strip()
            if not line or line[0] == '#':
                continue
            field = None
            if line[0] == '[':
                m = pattern.match(line)
                if m:
                    field = m.group(1)
                else:
                    raise ConanException("ConfigParser: Bad syntax '%s'" % line)
            if field:
                if self._allowed_fields and field not in self._allowed_fields and raise_unexpected_field:
                    raise ConanException("ConfigParser: Unrecognized field '%s'" % field)
                else:
                    current_lines = []
                    self._sections[field] = current_lines
            else:
                if current_lines is None:
                    raise ConanException("ConfigParser: Unexpected line '%s'" % line)
                line = line.strip()
                if parse_lines:
                    tmp = line.split("#")
                    if len(tmp) > 1:
                        try:
                            # A reference with revision could be interpreted as a comment
                            if len(tmp) > 2:  # Reference with revision and comments?
                                if tmp[1].startswith(" "):  # Not a valid revision
                                    raise ConanException()
                                line = tmp[0] + "#" + tmp[1].rstrip()
                                ConanFileReference.loads(line)
                            elif len(tmp) == 2:
                                ConanFileReference.loads(line)
                        except ConanException:
                            line = tmp[0].strip()

                current_lines.append(line)

    def __getattr__(self, name):
        if name in self._sections:
            return "\n".join(self._sections[name])
        else:
            if self._allowed_fields and name in self._allowed_fields:
                return ""
            else:
                raise ConanException("ConfigParser: Unrecognized field '%s'" % name)
