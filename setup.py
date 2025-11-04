from pathlib import Path
from setuptools import setup, find_packages

BASE_DIR = Path(__file__).resolve().parent
with open(BASE_DIR / "LICENSE") as file:
    _license = file.read()

with open(BASE_DIR / "README.md") as file:
    description = file.read()

setup(
    name="aqilas-sms",
    version="0.0.1",
    long_description=description,
    long_description_content_type="text/markdown",
    url="https://github.com/parice02/aqilas-sms",
    description="Library for sending sms",
    packages=find_packages(include=["sms"]),
    author="Mohamed Zeba",
    author_email="<parice02@hotmail.com>",
    license=_license,
    classifiers=[
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    install_requires=["requests>=2.31.0"],
)
