"""Legacy editable-install bridge for older pip versions."""
from setuptools import find_packages, setup


setup(
    name="jev-anything",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages("src"),
    python_requires=">=3.10",
    install_requires=["requests>=2.31", "pexpect>=4.9", "pyte>=0.8"],
)
