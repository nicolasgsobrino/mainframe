from __future__ import annotations

from setuptools import find_packages, setup

setup(
    name="aws-mainframe-modernization-carddemo-python",
    version="0.1.0",
    packages=find_packages(include=["carddemo*", "models*", "screens*", "services*", "workers*"]),
    include_package_data=True,
    package_data={"screens": ["templates/screens/*.html"]},
    python_requires=">=3.11",
    install_requires=[
        "django>=5.0,<6.0",
        "psycopg[binary]>=3.2,<4.0",
        "typer>=0.12,<1.0",
        "pika>=1.3,<2.0",
        "pytest>=8.0,<9.0",
        "pytest-django>=4.8,<5.0",
    ],
)
