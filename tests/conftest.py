import json
from contextlib import contextmanager


@contextmanager
def does_not_raise():
    yield


def pretty_dump(data) -> str:
    return json.dumps(data, indent=4, sort_keys=True)
