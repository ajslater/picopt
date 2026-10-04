"""
Answer ``picopt doctor``: will a run with these options work, and if not, why.

The doctor takes every run option and path, then reports the environment,
picopt's Python dependencies, the plugins that failed to load, the full tool
inventory, the layered config, what the run does with each enabled format, and
each path's ``.picopt.yaml`` files and timestamps. It never writes. The exit
code is 1 when a row fails: the run would error out or skip an enabled format.
"""

from picopt.doctor.checkup import PicoptDoctor

__all__ = ("PicoptDoctor",)
