#!/usr/bin/env python

from distutils.core import setup

setup(
    name="nanogenmo2019",
    version="1.0",
    description="Python Distribution Utilities",
    author="Will Thompson",
    author_email="will@willthompson.co.uk",
    url="https://github.com/wjt/nanogenmo/blob/master/2019",
    scripts=["2019/nanogenpo"],
    install_requires=["polib"],
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Topic :: Artistic Software",
    ],
)
