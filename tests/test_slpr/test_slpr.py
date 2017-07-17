import os
import random
import imp
import shutil

try:
    import json
except ImportError:
    import simplejson as json

TEST_FILE_DIR = os.path.realpath(os.path.dirname(__file__))
SLPR_MODULE   = os.path.realpath(os.path.join(TEST_FILE_DIR, '..', '..', 'slpr.py'))
REPO_DIR = os.path.join(os.path.dirname(__file__), 'fixtures', 'test_repository')


def _load_module(modname, modfile):
    import imp
    return imp.load_source(modname, modfile)


def test_install_plugin():

    slpr = _load_module('slpr', SLPR_MODULE)

    repo_dir = os.path.join(REPO_DIR, str(random.randint(1,1000)))
    plugin1_zip = os.path.join(os.path.dirname(__file__), 'fixtures', 'fake_plugin1', 'fake_plugin1.zip')
    plugin2_zip = os.path.join(os.path.dirname(__file__), 'fixtures', 'fake_plugin1-newversion', 'fake_plugin1-newversion.zip')

    try:
        args = [
            'install-plugin',
            '-r',
            repo_dir,
            '-p',
            plugin1_zip
        ]

        slpr.run(args)

        args[4] = plugin2_zip

        slpr.run(args)

        for ver in ['0.0.1', '0.1.0']:
            plugin_dir = os.path.join(repo_dir, 'testenv', 'fake_plugin1', ver)

            expected_files = [
                os.path.join(plugin_dir, 'testenv.fake_plugin1-%s.zip' % ver),
                os.path.join(plugin_dir, 'testenv.fake_plugin1-%s.zip.md5' % ver),
                os.path.join(plugin_dir, 'testenv.fake_plugin1-%s.zip.sha256' % ver),
                os.path.join(plugin_dir, 'metadata.json'),
                os.path.join(plugin_dir, 'metadata.json.md5'),
                os.path.join(plugin_dir, 'metadata.json.sha256')
            ]

            for expected_file in expected_files:
                assert os.path.exists(expected_file)

        plugin_db_file = os.path.join(repo_dir, 'plugins.json')

        assert os.path.exists(plugin_db_file)

        plugin_db = json.load(open(plugin_db_file))

        assert plugin_db['testenv']['fake_plugin1']['latest'] == '0.1.0'
        assert plugin_db['testenv']['fake_plugin1']['versions'] == ['0.0.1','0.1.0']

        assert plugin_db['types'] == ['testenv']

    finally:
        if os.path.exists(repo_dir):
            shutil.rmtree(repo_dir)

