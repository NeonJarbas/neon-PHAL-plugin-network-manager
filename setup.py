#!/usr/bin/env python3
from setuptools import setup

PLUGIN_ENTRY_POINT = 'neon-phal-network-manager=neon_phal_network_manager:NetworkManagerEvents'
setup(
    name='neon-phal-network-manager',
    version='0.0.1a1',
    description='A PHAL plugin for mycroft',
    url='https://github.com/NeonGeckoCom/neon-PHAL-plugin-network-manager',
    author='JarbasAi',
    author_email='jarbasai@mailfence.com',
    license='Apache-2.0',
    packages=['neon_phal_network_manager'],
    install_requires=["ovos-plugin-manager>=0.0.1", "dbus-next"],
    zip_safe=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Text Processing :: Linguistic',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    entry_points={'ovos.plugin.phal': PLUGIN_ENTRY_POINT}
)
