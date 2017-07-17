#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""slpr.py - Sourcelyzer Plugin Repository Tool

This tool handles various tasks for managing a sourcelyzer plugin repository.

Plugin Structure:
    root
    | - __init__.py         The plugin will be loaded as a python module. Use
    |                       __init__.py to expose a class called Plugin.
    | - plugin.ini          Metadata file of the plugin.

You can include any other file in the root directory of the plugin, but these
two files must exist within the zip file.


plugin.ini format:
[plugin]
name=[plugin name]
type=[plugin type]
version=[plugin version]
description=[plugin description]
author=[plugin author]
url=[plugin url]

Plugin versions must follow the Semver format.


Directory Structure:
    root
    | - plugins.json        A JSON list of available plugins
    | - plugins.json.md5    A MD5 hash of plugins.json
    | - plugins.json.sha256 A SHA256 hash of plugins.json
    | - [plugin type]
        | - [plugin name]
            | - [plugin version]
                | - metadata.json         Metadata of a plugin
                | - metadata.json.md5     MD5 hash of metadata.json
                | - metadata.json.sha256  SHA256 hash of metadata.json
                | - [type].[name].[version].zip
                |                         Zip file of the plugin.
                | - [type].[name].[version].zip.md5
                |                         MD5 hash of the plugin zip file
                | - [type].[name].[version].zip.sha256
                |                         SHA256 hash of the plugin zip filename

plugins.json format:
{
    "[type]": {
        "[name]": {
            "versions": ["0.0.1","0.0.2",...],
            "latest": "0.0.2",
            "0.0.1": {
                "md5": "[plugin zip md5]"
                "sha256": "[plugin zip sha256]"
            },
            ...
        }
    }
}

metadata.json format
{
    "version": "[plugin version]",
    "name": "[plugin name]",
    "author": "[plugin author]",
    "url": "[plugin url]",
    "install_date": "[date when plugin was added to repository]",
    "hashes": {
        "md5": "[plugin zip md5]",
        "sha256": "[plugin zip sha256]"
    },
    "type": "[plugin type]",
    "description": "[plugin description]"
}


Install a Plugin:
    slpr.py install-plugin -r REPOSITORY -p PLUGIN

    Use this to install a plugin from a plugin zip file into a repository.
    If REPOSITORY doesn't exist, then it will be created.

    Options:

        REPOSITORY: The directory of the repository you want to install the
                   plugin to.

        PLUGIN:     A path or URL to a plugin zip file

Refresh/Create a Repository:
    slpr.py refresh-repo -r REPOSITORY

    Use this to refresh an existing repository or create a new one. This will
    recreate your plugins.json file.

    Options:

        REPOSITORY: The directory of the repository. If it does not exist
                    it will be created automatically.
"""

import hashlib
import logging
import os
import re
import shutil
import zipfile
import tempfile
import datetime
import fnmatch
import sys
import argparse

try:
    import simplejson as json
except ImportError:
    import json

try:
    import ConfigParser as configparser
except ImportError:
    import configparser

if not hasattr(__builtins__, 'cmp'):
    def cmp(cmp_a, cmp_b):
        """python2.7 cmp() function"""
        return (cmp_a > cmp_b) - (cmp_a < cmp_b)

SEMVER_REGEX = re.compile(r"""
^
(?P<major>(?:0|[1-9][0-9]*))
\.
(?P<minor>(?:0|[1-9][0-9]*))
\.
(?P<patch>(?:0|[1-9][0-9]*))
(\-(?P<prerelease>
(?:0|[1-9A-Za-z-][0-9A-Za-z-]*)
(\.(?:0|[1-9A-Za-z-][0-9A-Za-z-]*))*
))?
(\+(?P<build>
  [0-9A-Za-z-]+
  (\.[0-9A-Za-z-]+)*
))?
$
""", re.VERBOSE)


def parse_args(argv):
    """Parse an argv array"""
    parser = argparse.ArgumentParser()

    sub_parser = parser.add_subparsers()

    install_args = sub_parser.add_parser('install-plugin', help='Install a plugin to a repository.')
    install_args.add_argument(
        '-p',
        '--plugin',
        action='store',
        required=True,
        help='Location of the plugin zip file. Can also point to a URL'
    )

    repo_help = 'Location of the repository. If the repository does not exist, it will be created'
    install_args.add_argument('-r', '--repository', action='store', required=True, help=repo_help)

    refresh_help = 'Refresh an existing repository or create a new one'
    refresh_args = sub_parser.add_parser('refresh-repo', help=refresh_help)
    refresh_args.add_argument('-r', '--repository', action='store', required=True, help=repo_help)

    args = parser.parse_args(argv)

    cmd = argv[0]
    return (cmd, vars(args))


def parse_version(version):
    """Parse a semver string - taken from semver python lib"""
    match = SEMVER_REGEX.match(version)
    if match is None:
        raise ValueError('%s is not a valid SemVer string' % version)

    version_parts = match.groupdict()
    version_parts['major'] = int(version_parts['major'])
    version_parts['minor'] = int(version_parts['minor'])
    version_parts['patch'] = int(version_parts['patch'])

    return version_parts


def compare_versions(version1, version2):
    """Compare two semver strings - taken from semver python lib"""
    version1 = parse_version(version1)
    version2 = parse_version(version2)

    for key in ['major', 'minor', 'patch']:
        version_cmp = cmp(version1.get(key), version2.get(key))
        if version_cmp:
            return version_cmp

    prerelease1, prerelease2 = version1.get('prerelease'), version2.get('prerelease')
    prerelease_cmp = _nat_cmp(prerelease1, prerelease2)

    if not prerelease_cmp:
        return 0
    if not prerelease1:
        return 1
    elif not prerelease2:
        return -1

    return prerelease_cmp


class SemverKeySort():
    def __init__(self, version):
        """SemverKeySort used for key argument of sorted()"""
        self.version = version

    def __lt__(self, other_version):
        val = compare_versions(self.version, other_version.version)
        return val < 0

    def __gt__(self, other_version):
        val = compare_versions(self.version, other_version.version)
        return val > 0

    def __eq__(self, other_version):
        return self.version == other_version.version


def _nat_cmp(compare_a, compare_b):
    """Natural comparison? Taken from semver python lib"""
    def convert(text):
        return int(text) if re.match('[0-9]+', text) else text

    def split_key(key):
        return [convert(c) for c in key.split('.')]

    def cmp_prerelease_tag(compare_a, compare_b):
        if isinstance(compare_a, int) and isinstance(compare_b, int):
            return cmp(compare_a, compare_b)
        elif isinstance(compare_a, int):
            return -1
        elif isinstance(compare_b, int):
            return 1
        else:
            return cmp(compare_a, compare_b)

    compare_a, compare_b = compare_a or '', compare_b or ''
    a_parts, b_parts = split_key(compare_a), split_key(compare_b)
    for sub_a, sub_b in zip(a_parts, b_parts):
        cmp_result = cmp_prerelease_tag(sub_a, sub_b)
        if cmp_result != 0:
            return cmp_result
    else:
        return cmp(len(compare_a), len(compare_b))


def file_hash(filename, hasher):
    """Calculate a hash sum of a file"""
    blocksize = 65536

    with open(filename, 'rb') as fobj:
        block = fobj.read(blocksize)

        block_len = len(block)

        if block_len > 0:
            hasher.update(block)

    return hasher.hexdigest()


def file_sums(filename):
    md5sum = file_hash(filename, hashlib.md5())
    sha256sum = file_hash(filename, hashlib.sha256())
    return (md5sum, sha256sum)


def install_plugin(plugin_zip, repo_dir, log=None):
    """Install a plugin to a repository"""
    repo_dir = os.path.abspath(repo_dir)
    plugin_zip = os.path.abspath(plugin_zip)

    if log is None:
        log = logging.getLogger('install-plugin')

    log.info('Repository Direcotry: %s' % repo_dir)
    log.info('Plugin: %s' % plugin_zip)

    if not os.path.exists(repo_dir):
        refresh_repository(repo_dir)

    if not os.path.exists(plugin_zip):
        raise OSError('Plugin does not exist: %s' % plugin_zip)

    zip_ref = zipfile.ZipFile(plugin_zip, 'r')

    tmpdirname = tempfile.mkdtemp(prefix='splr')

    try:
        log.info('Extracting plugin zip file')
        zip_ref.extractall(tmpdirname)

        config = configparser.ConfigParser()
        config.read(tmpdirname + '/plugin.ini')

        print(config.__dict__)

        plugin_name = config.get('plugin', 'name')
        plugin_type = config.get('plugin', 'type')
        plugin_version = config.get('plugin', 'version')

        plugin_key = '%s.%s-%s' % (plugin_type, plugin_name, plugin_version)

        log.info('Detected plugin: %s' % plugin_key)

        plugin_dir = os.path.join(repo_dir, plugin_type, plugin_name, plugin_version)

        if not os.path.exists(plugin_dir):
            os.makedirs(plugin_dir)

        log.info('Creating hash sums')

        md5sum, sha256sum = file_sums(plugin_zip)

        with open('%s.zip.md5' % os.path.join(plugin_dir, plugin_key), 'w') as f:
            f.write(md5sum)

        with open('%s.zip.sha256' % os.path.join(plugin_dir, plugin_key), 'w') as f:
            f.write(sha256sum)

        log.info('MD5: %s' % md5sum)
        log.info('SHA256: %s' % sha256sum)

        log.info('Copying file to repo')
        shutil.copy(plugin_zip, os.path.join(plugin_dir, plugin_key + '.zip'))

        log.info('Creating metadata file')

        plugin_data = {
            'name': plugin_name,
            'type': plugin_type,
            'version': plugin_version,
            'description': config.get('plugin', 'description'),
            'author': config.get('plugin', 'author'),
            'url': config.get('plugin', 'url'),
            'install_date': datetime.datetime.utcnow().isoformat(),
            'hashes': {
                'md5': md5sum,
                'sha256': sha256sum
            }
        }

        plugin_metadata_fn = os.path.join(plugin_dir, 'metadata.json')

        with open('%s' % plugin_metadata_fn, 'w') as f:
            f.write(json.dumps(plugin_data, indent=2))

        metadata_md5, metadata_sha = file_sums(os.path.join(plugin_dir, 'metadata.json'))

        with open('%s.md5' % plugin_metadata_fn, 'w') as f:
            f.write(metadata_md5)

        with open('%s.sha256' % plugin_metadata_fn, 'w') as f:
            f.write(metadata_sha)
    finally:
        shutil.rmtree(tmpdirname)


def refresh_repository(repo_dir, log=None):
    if log is None:
        log = logging.getLogger('refresh-plugins')

    plugin_db = {
        'types': []
    }

    repo_dir = os.path.abspath(repo_dir)

    if not os.path.exists(repo_dir):
        log.info('Creating repository at %s' % repo_dir)
        os.makedirs(repo_dir)
    else:
        log.info('Scanning repository at %s' % repo_dir)

    total_plugins = 0
    total_versions = 0

    fns = []

    for root, dirnames, filenames in os.walk(repo_dir):
        for filename in fnmatch.filter(filenames, 'metadata.json'):
            fns.append(os.path.join(root, filename))

    for fn in fns:
        with open(fn, 'r') as f:
            meta = json.load(f)

            plugin_key = '%s.%s-%s' % (meta['type'], meta['name'], meta['version'])

            log.info('Found plugin: %s' % plugin_key)

            if meta['type'] not in plugin_db['types']:
                plugin_db['types'].append(meta['type'])

            if meta['type'] not in plugin_db:
                plugin_db[meta['type']] = {}

            if meta['name'] not in plugin_db[meta['type']]:
                plugin_db[meta['type']][meta['name']] = {
                    'latest': None,
                    'versions': []
                }

            plugin_metadata = plugin_db[meta['type']][meta['name']]

            if meta['version'] not in plugin_metadata['versions']:
                plugin_metadata['versions'].append(meta['version'])

            plugin_db[meta['type']][meta['name']] = plugin_metadata

    for t in plugin_db['types']:
        for name in plugin_db[t]:
            total_plugins += 1
            sorted_versions = sorted(plugin_db[t][name]['versions'], key=SemverKeySort)
            total_versions = total_versions + len(sorted_versions)
            plugin_db[t][name]['versions'] = sorted_versions
            plugin_db[t][name]['latest'] = sorted_versions[-1:][0]

    log.info('Total Plugins: %s' % total_plugins)
    log.info('Total Versions: %s' % total_versions)

    plugin_db_file = os.path.join(repo_dir, 'plugins.json')

    log.info('Writing repo db file: %s' % plugin_db_file)

    with open(plugin_db_file, 'w') as f:
        f.write(json.dumps(plugin_db, indent=2))

    md5sum, sha256sum = file_sums(plugin_db_file)

    with open(plugin_db_file + '.md5', 'w') as f:
        f.write(md5sum)

    with open(plugin_db_file + '.sha256', 'w') as f:
        f.write(sha256sum)


def install(plugin, repo):
    if not os.path.exists(repo):
        refresh_repository(repo)

    print(plugin, repo)

    install_plugin(plugin, repo)
    refresh_repository(repo)


def refresh(repo):
    refresh_repository(repo)


def run(argv):

    cmd, args = parse_args(argv)

    if cmd == 'install-plugin':
        install(args['plugin'], args['repository'])
    elif cmd == 'refresh-repo':
        refresh(args['repository'])

if __name__ == '__main__':
    run(sys.argv[1:])
