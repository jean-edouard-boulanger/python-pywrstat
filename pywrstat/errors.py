class Error(Exception):
    pass


class MissingBinary(Exception):
    pass


class NotReady(Error):
    pass


class Unreachable(NotReady):
    pass


class CommandFailed(Error):
    pass


class SetupFailed(CommandFailed):
    pass


class Timeout(Error):
    pass
