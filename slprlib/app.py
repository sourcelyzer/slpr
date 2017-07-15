import cherrypy
import time
import threading
import os
import zipfile
import tempfile
import hashlib
import configparser
import simplejson as json
import shutil
import glob
import sys
import semver
import datetime
import mimetypes
from slpr.utils import install_plugin, refresh_plugins
from slpr.rest.browser import RepositoryBrowser
from sllib import RESTResource

class RepoDb(RESTResource):
    def __init__(self, repo_dir):
        self.repo_dir = repo_dir

    def handle_GET(self, *vpath, **params):
        cherrypy.response.headers['Content-Type'] = 'application/json'

        with open(self.repo_dir + '/plugins.json', 'rb') as f:
            return json.loads(f.read())

    def handle_POST(self, *vpath, **params):

        tmp_dir = os.path.join(self.repo_dir, 'tmp')

        if not os.path.exists(tmp_dir):
            os.mkdir(tmp_dir)

        tmp_zip_file = os.path.join(tmp_dir, hashlib.md5(os.urandom(32)).hexdigest() + '.zip')
        with open(tmp_zip_file, 'wb') as f:
            shutil.copyfileobj(cherrypy.request.body, f)

        install_plugin(tmp_zip_file, self.repo_dir)

        os.remove(tmp_zip_file)

        return self.handle_GET()

        return {
            'ok': True
        }



class ServerThread(threading.Thread):
    def __init__(self, config, *args, **kwargs):
        threading.Thread.__init__(self, *args, **kwargs)
        self._running = False
        self.config = config

    def run(self):

        try:
            self._running = True
            plugin_dir = os.path.abspath(self.config['slpr.repo_dir'])

            if not os.path.exists(plugin_dir):
                os.makedirs(plugin_dir)


            icon_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'assets/icons')
            print('icon path: %s' % icon_path)

            cherrypy.config.update({
                'server.socket_host':  self.config['slprd.server.listen_addr'],
                'server.socket_port': int(self.config['slprd.server.listen_port'])
            })

            cherrypy.tree.mount(RepositoryBrowser(plugin_dir), '/', config={'/': {}, '/icons': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': icon_path
                }})

           # cherrypy.tree.mount(RepoDb(plugin_dir), '/db', {'/': {}})
           # cherrypy.tree.mount(Repository(plugin_dir), '/repo', {'/': {}})

            print('starting server at http://%s:%s' % (
                self.config['slprd.server.listen_addr'],
                self.config['slprd.server.listen_port']
            ), flush=True)
            cherrypy.engine.start()
            cherrypy.engine.block()
        finally:
            self._running = False

    def stop(self):
        cherrypy.engine.stop()
        cherrypy.engine.exit()


class App():
    def __init__(self, config):
        self.config = config
        self._running = False

    def run(self):
        self._running = True
        server = ServerThread(self.config)
        server.start()

        while self._running:
            try:
                time.sleep(1)
                if not server._running:
                    self._running = False
            except KeyboardInterrupt:
                server.stop()
                server._running = False


