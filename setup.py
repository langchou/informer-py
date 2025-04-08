from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="informer",
    version="1.0.0",
    description="Chiphell二手区监控工具",
    author="langchou",
    author_email="",
    packages=find_packages(),
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "informer=informer.main:main",
        ],
    },
) 