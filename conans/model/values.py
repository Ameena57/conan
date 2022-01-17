from conans.errors import ConanException


class Values(object):
    def __init__(self, value="values"):
        self._value = str(value)
        self._dict = {}  # {key: Values()}

    def __getattr__(self, attr):
        if attr not in self._dict:
            return None
        return self._dict[attr]

    def __delattr__(self, attr):
        if attr not in self._dict:
            return
        del self._dict[attr]

    def clear(self):
        # TODO: Test. DO not delete, might be used by package_id() to clear settings values
        self._dict.clear()
        self._value = ""

    def __setattr__(self, attr, value):
        if attr[0] == "_":
            return super(Values, self).__setattr__(attr, value)
        self._dict[attr] = Values(value)

    def copy(self):
        """ deepcopy, recursive
        """
        result = Values(self._value)
        for k, v in self._dict.items():
            result._dict[k] = v.copy()
        return result

    @property
    def fields(self):
        """ return a sorted list of fields: [compiler, os, ...]
        """
        return sorted(list(self._dict.keys()))

    def __bool__(self):
        return self._value.lower() not in ["false", "none", "0", "off", ""]

    def __str__(self):
        return self._value

    def __eq__(self, other):
        return str(other) == self.__str__()

    @classmethod
    def loads(cls, text):
        result = []
        for line in text.splitlines():
            if not line.strip():
                continue
            name, value = line.split("=", 1)
            result.append((name.strip(), value.strip()))
        return cls.from_list(result)

    def as_list(self, list_all=True):
        result = []
        for field in self.fields:
            value = getattr(self, field)
            if value or list_all:
                result.append((field, str(value)))
                child_lines = value.as_list()
                for (child_name, child_value) in child_lines:
                    result.append(("%s.%s" % (field, child_name), child_value))
        return result

    @classmethod
    def from_list(cls, data):
        result = cls()
        for (field, value) in data:
            tokens = field.split(".")
            attr = result
            for token in tokens[:-1]:
                attr = getattr(attr, token)
                if attr is None:
                    raise ConanException("%s not defined for %s\n"
                                         "Please define %s value first too"
                                         % (token, field, token))
            setattr(attr, tokens[-1], Values(value))
        return result

    def serialize(self):
        return self.as_list()

    def dumps(self):
        items = self.as_list(list_all=False)
        if not items:
            return ""
        result = []
        for (name, value) in items:
            # It is important to discard None values, so migrations in settings can be done
            # without breaking all existing packages SHAs, by adding a first "None" option
            # that doesn't change the final sha
            if value != "None":
                result.append("%s=%s" % (name, value))
        result.append("")
        return '\n'.join(result)
