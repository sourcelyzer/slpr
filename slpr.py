#!/usr/bin/env python   
import hashlib
import logging
import os, re, shutil
import zipfile
import tempfile
import datetime
import fnmatch
import sys
import argparse

try: import simplejson as json
except ImportError: import json

try: import ConfigParser as configparser
except ImportError: configparser

SEMVER_REGEX = re.compile(
        r"""
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

    parser = argparse.ArgumentParser()

    sp = parser.add_subparsers()
    install = sp.add_parser('install-plugin', help='Install a plugin to a repository.')
    install.add_argument('-p', '--plugin', action='store', help='Location of the plugin zip file. Can also point to a URL', required=True)
    install.add_argument('-r', '--repository', action='store', help='Location of the repository. If the reository does not exist, it will be created.', required=True)

    refresh = sp.add_parser('refresh-repo', help='Refresh an existing repository or create a new one.')
    refresh.add_argument('-r', '--repository', action='store', help='Location of the repository. If the reository does not exist, it will be created.', required=True)
    args = parser.parse_args(argv)

    cmd = argv[0]
    return (cmd, vars(args))

def parse_version(version):
    match = SEMVER_REGEX.match(version)
    if match is None:
        raise ValueError('%s is not a valid SemVer string' % version)

    version_parts = match.groupdict()
    version_parts['major'] = int(version_parts['major'])
    version_parts['minor'] = int(version_parts['minor'])
    version_parts['patch'] = int(version_parts['patch'])

    return version_parts


def compare_versions(v1, v2):
    v1 = parse_version(v1)
    v2 = parse_version(v2)

    for key in ['major', 'minor', 'patch']:
        v = cmp(v1.get(key), v2.get(key))
        if v:
            return v

    rc1, rc2 = v1.get('prerelease'), d2.get('prerelease')
    rccmp = _nat_cmp(rc1, rc2)

    if not rccmp:
        return 0
    if not rc1:
        return 1
    elif not rc2:
        return -1

    return rccmp


def _nat_cmp(a, b):
    def convert(text):
        return int(text) if re.match('[0-9]+', text) else text

    def split_key(key):
        return [convert(c) for c in key.split('.')]

    def cmp_prerelease_tag(a, b):
        if isinstance(a, int) and isinstance(b, int):
            return cmp(a, b)
        elif isinstance(a, int):
            return -1
        elif isinstance(b, int):
            return 1
        else:
            return cmp(a, b)

    a, b = a or '', b or ''
    a_parts, b_parts = split_key(a), split_key(b)
    for sub_a, sub_b in zip(a_parts, b_parts):
        cmp_result = cmp_prerelease_tag(sub_a, sub_b)
        if cmp_result != 0:
            return cmp_result
    else:
        return cmp(len(a), len(b))

def hash_bytestr_iter(bytesiter, hasher, ashexstr=False):
    for block in bytesiter:
        hasher.update(block)
    return hasher.hexdigest() if ashexstr else hasher.digest()

def file_as_blockiter(afile, blocksize=65536):
    with afile:
        block = afile.read(blocksize)
        while len(block) > 0:
            yield block
            block = afile.read(blocksize)

def file_sums(fn):
    md5sum = hash_bytestr_iter(file_as_blockiter(open(fn, 'rb')), hashlib.md5(), ashexstr=True)
    sha256sum = hash_bytestr_iter(file_as_blockiter(open(fn, 'rb')), hashlib.sha256(), ashexstr=True)
    return (md5sum, sha256sum)


def install_plugin(fn, repo_dir, log=None):

    repo_dir = os.path.abspath(repo_dir)
    fn = os.path.abspath(fn)

    if log == None:
        log = logging.getLogger('install-plugin')

    log.info('Repository Direcotry: %s' % repo_dir)
    log.info('Plugin: %s' % fn)

    if not os.path.exists(repo_dir):
        raise FileNotFoundError('Repository directory does not exist: %s' % repo_dir)

    if not os.path.exists(fn):
        raise FileNotFoundError('Plugin does not exist: %s' % fn)

    zip_ref = zipfile.ZipFile(fn, 'r')

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

        md5sum, sha256sum = file_sums(fn)

        with open('%s.zip.md5' % os.path.join(plugin_dir, plugin_key), 'w') as f:
            f.write(md5sum)

        with open('%s.zip.sha256' % os.path.join(plugin_dir, plugin_key), 'w') as f:
            f.write(sha256sum)

        log.info('MD5: %s' % md5sum)
        log.info('SHA256: %s' % sha256sum)

        log.info('Copying file to repo')
        shutil.copy(fn, os.path.join(plugin_dir, plugin_key + '.zip'))

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
    if log == None:
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

    glob_ptn = '%s/*/*/*/metadata.json' % repo_dir

    total_plugins = 0
    total_versions = 0

    fns = []

    for root, dirnames, filenames in os.walk(repo_dir):
        for filename in fnmatch.filter(filenames, 'metadata.json'):
            fns.append(os.path.join(root, filename))


    #for fn in glob.glob(glob_ptn, recursive=True):
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
            sorted_versions = sorted(plugin_db[t][name]['versions'], cmp=compare_versions)
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


