#!/usr/bin/env python
from docopt import docopt
from slpr.app import App, install_plugin, refresh_plugins
from slpr.properties import load_from_file

__doc__="""Slrpd - The SourceLyzer RePo Daemon

Usage: slprd start-console [options]
       slprd add-plugin PLUGIN_URL [options]
       slprd refresh-plugins [options]

Options:
    -c --conf FILENAME      Location of the configuration file
    -h --help               This help
"""

if __name__ == '__main__':
    args = docopt(__doc__)
    print(args)

    conf_file = args['--conf'] if args['--conf'] else './conf/slpr.properties'
    conf = load_from_file(conf_file)

    if args['add-plugin']:
        install_plugin(args['PLUGIN_URL'], conf['slpr.repo_dir'])
    elif args['refresh-plugins']:
        refresh_plugins(conf['slpr.repo_dir'])
    elif args['start-console']:
        app = App(conf)
        app.run()


    """
    conf_file = args['--conf'] if args['--conf'] else './conf/slpr.properties'

    print('Configuration file: %s' % conf_file)

    conf = load_from_file(conf_file)

    app = App(conf)
    app.run()
    """
