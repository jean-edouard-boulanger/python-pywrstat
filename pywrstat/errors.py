class PywrstatError(Exception):
    """Base class for all pywrstat errors."""

    pass


class MissingBinary(PywrstatError):
    """Pywrstat could not locate the pwrstat binary. It's either not installed on the local computer, or not located
    where pywrstat expects it (``/sbin/pwrstat`` by default)
    """

    pass


class NotReady(PywrstatError):
    """The UPS was not ready to perform de requested operation."""

    pass


class Unreachable(NotReady):
    """An operation could not be completed because the UPS was not reachable."""

    pass


class CommandFailed(PywrstatError):
    """An operation failed to complete."""

    pass


class SetupFailed(CommandFailed):
    """A setup operation could not be completed."""

    pass


class Timeout(PywrstatError):
    """An operation could not be completed within the allocated time."""

    pass
