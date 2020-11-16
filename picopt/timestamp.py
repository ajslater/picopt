"""Timestamp writer for keeping track of bulk optimizations."""
from picopt import PROGRAM_NAME
from picopt.timestamp_base import TimestampBase


class Timestamp(TimestampBase):
    """Picopt timestamps."""

    OLD_TIMESTAMP_NAME = f".{PROGRAM_NAME}_timestamp"
    TIMESTAMPS_NAME = f".{PROGRAM_NAME}_timestamps.yaml"
