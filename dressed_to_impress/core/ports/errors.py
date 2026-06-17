"""Errors that infrastructure adapters may raise.

Defined in the Core so adapters depend inward only. The use case catches these and
translates them into AppResult.failure(...), keeping exceptions out of the public
service signature.
"""

from __future__ import annotations


class InfraError(Exception):
    """Raised by an adapter when an out-of-process concern fails."""
