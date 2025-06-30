#!/bin/env python
"""Test colors."""

from termcolor import cprint

colors = (
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
    "light_grey",
    "dark_grey",
    "light_red",
    "light_green",
    "light_yellow",
    "light_blue",
    "light_magenta",
    "light_cyan",
)

attrs = ("bold", "dark")

for color in colors:
    cprint(color, color)
    for attr in attrs:
        cprint(f"{color} {attr}", color, attrs=[attr])
    cprint(f"{color} {' '.join(reversed(attrs))}", color, attrs=attrs)
