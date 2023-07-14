# type: ignore
import pathlib

import setuptools

HERE = pathlib.Path(__file__).parent
README = (HERE / "README.md").read_text()

__version__ = "0.0.0"
exec(open("pywrstat/version.py").read())  # export __version__


setuptools.setup(
    name="pywrstat",
    version=__version__,
    description="Pwrstat (CyberPower UPS Linux command line) Python wrapper API",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Jean-Edouard Boulanger",
    url="https://github.com/jean-edouard-boulanger/pywrstat",
    author_email="jean.edouard.boulanger@gmail.com",
    license="MIT",
    packages=["pywrstat"],
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: System :: Power (UPS)",
    ],
    install_requires=[
        "python-dateutil>=2.8.2,<3",
        "pydantic>=2.0.2,<3",
        "Flask>=2.3.2,<3",
        "gunicorn>=20.1.0,<21",
        "PyJWT>=2.7.0,<3",
        "python-dotenv>=1.0.0,<2",
    ],
)
