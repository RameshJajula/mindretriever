#!/usr/bin/env python
"""Traditional setup.py for compatibility."""

from setuptools import setup, find_packages

setup(
    name="mindretriever",
    version="0.2.0",
    packages=find_packages(include=["graphmind*", "mindretriever*"]),
    python_requires=">=3.10",
)
