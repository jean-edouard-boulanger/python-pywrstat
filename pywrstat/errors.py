class Error(Exception):
    pass


class MissingBinary(Exception):
    pass


class Unreachable(Error):
    pass


class CommandFailed(Error):
    pass


class SetupFailed(CommandFailed):
    pass


class Timeout(Error):
    pass
