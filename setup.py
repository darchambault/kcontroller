from setuptools import find_packages
from setuptools import setup

try:
    with open('target/version') as f:
        version = f.readline().strip()
except:
    version = None

setup(
    name='kcontroller',
    version=version,
    install_requires=[
        'Flask==0.10.1',
        'gunicorn==19.1.0',
        'websocket-client==0.16.0a',
        'pyusb==1.0.0b1',
    ],
    packages=find_packages(
        exclude=[
            "*.tests", "*.tests.*", "tests.*", "tests"
        ]
    ),
    entry_points={'console_scripts': [
        'kcontroller=kcontroller.main:run',
        ]
    },
    package_data={
        'kcontroller': [
            'resources/upstart-script',
        ]
    }

)
