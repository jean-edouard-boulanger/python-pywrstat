.. pywrstat documentation master file, created by
   sphinx-quickstart on Sat Jul 23 11:44:39 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Pywrstat documentation
====================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Pywrstat client
-------------------------

.. autoclass:: pywrstat.client.Pywrstat
   :members:

Entities
--------

.. autoclass:: pywrstat.dto.DaemonConfiguration
   :members:

.. autoclass:: pywrstat.dto.Event
   :members:

.. autoclass:: pywrstat.dto.LowBatteryAction
   :members:

.. autoclass:: pywrstat.dto.PowerEvent
   :members:

.. autoclass:: pywrstat.dto.PowerFailureAction
   :members:

.. autoclass:: pywrstat.dto.ReachabilityChanged
   :members:

.. autoenum:: pywrstat.dto.TestStatus
   :members:

.. autoclass:: pywrstat.dto.TestResult
   :members:

.. autoclass:: pywrstat.dto.UPSStatus
   :members:

.. autoclass:: pywrstat.dto.UPSProperties
   :members:

.. autoclass:: pywrstat.dto.ValueChanged
   :members:


Errors
------

.. autoclass:: pywrstat.errors.PywrstatError
   :show-inheritance:
   :members:

.. autoclass:: pywrstat.errors.MissingBinary
   :show-inheritance:
   :members:

.. autoclass:: pywrstat.errors.NotReady
   :show-inheritance:
   :members:

.. autoclass:: pywrstat.errors.Unreachable
   :show-inheritance:
   :members:

.. autoclass:: pywrstat.errors.CommandFailed
   :show-inheritance:
   :members:

.. autoclass:: pywrstat.errors.SetupFailed
   :show-inheritance:
   :members:

.. autoclass:: pywrstat.errors.Timeout
   :show-inheritance:
   :members:
