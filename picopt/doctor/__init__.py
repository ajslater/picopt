"""
Answer ``picopt doctor``: will picopt work on this machine, and if not, why.

Reports the environment, picopt's Python dependencies, the plugins that
failed to load and the full tool inventory. The exit code is 1 when a check
fails.
"""

from picopt.doctor.checkup import PicoptDoctor

__all__ = ("PicoptDoctor",)
