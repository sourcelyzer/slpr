import cherrypy
import os
import mimetypes

ROW_TPL = """
<tr>
  <td>
    <img src="/icons/%(type)s-icon.svg" alt="%(type)s" width="16" height="16">
  </td>
  <td>
    <a href="%(url_path)s">%(fn)s</a>
  </td>
  <td>
    %(size)s
  </td>
  <td>
    %(lastmodified)s
  </td>
</tr>"""

HTML_START = """<!DOCTYPE html>
<html>
<head>
<title>Path: %(url_path)s</title>
</head>
<body>
<h1>Path: %(url_path)s</h1>
"""

HTML_PARENT_TPL = """<p><a href="%(url_path)s">Parent</a></p>"""

HTML_TABLE_START = """<table>
<thead>
  <tr>
    <th>Type</th>
    <th>Name</th>
    <th>Size</th>
    <th>Last Modified</th>
  </tr>
</thead>
<tbody>"""

HTML_TABLE_END = """</tbody></table>"""

HTML_END = "<p>Sourcelyzer</p></body></html>"


class RepositoryBrowser():

    def __init__(self, repo_dir, **kwargs):
        self.repo_dir = repo_dir
        self.row_tpl = ROW_TPL
        self.html_start = HTML_START
        self.html_end = HTML_END
        self.html_parent_tpl = HTML_PARENT_TPL
        self.html_table_start = HTML_TABLE_START
        self.html_table_end = HTML_TABLE_END

    @cherrypy.expose
    def default(self, *vpath, **kwargs):
        if '..' in vpath:
            raise cherrypy.HTTPError(400, 'Invalid Path')

        if len(vpath) == 0:
            vpath = ('.',)

        target_path = os.path.join(self.repo_dir, *vpath)
        target_path = os.path.realpath(target_path)

        if not target_path.startswith(self.repo_dir):
            raise cherrypy.HTTPError(404, 'Invalid path')

        if not os.path.exists(target_path):
            raise cherrypy.HTTPError(404, 'Invalid path')

        if os.path.isdir(target_path):
            return self.handle_DIR(target_path)
        elif os.path.isfile(target_path):
            return self.handle_FILE(target_path)
        else:
            raise cherrypy.HTTPError(400, 'Invalid path')


    def handle_FILE(self, target_path):

        size = os.path.getsize(target_path)
        mime = mimetypes.guess_type(target_path)[0]

        cherrypy.response.headers['Content-Type'] = mime
        cherrypy.response.headers['Content-Length'] = size

        f = open(target_path, 'rb')
        return f.read()

    def handle_DIR(self, target_path):

        target_url_path = target_path.replace(self.repo_dir, '')
        if target_url_path == '':
            target_url_path = '/'
            parent_path = None
        else:
            parent_path = os.path.join('/', *target_url_path.split('/')[:-1])
            target_url_path = target_url_path

        output = self.html_start % {
            'url_path': target_url_path
        }

        if parent_path != None:
            output += self.html_parent_tpl % { 'url_path': parent_path }


        output += self.html_table_start

        dirs = []
        files = []

        for f in os.listdir(target_path):
            url_path = os.path.join(target_url_path, f)
            full_path = os.path.join(target_path, f)

            if os.path.isdir(full_path):
                dirs.append((url_path, f, full_path))
            elif os.path.isfile(full_path):
                files.append((url_path, f, full_path))

        for url_path, fn, full_path in dirs:
            dir_html = self.row_tpl % {
                'type': 'folder',
                'url_path': url_path,
                'fn': fn,
                'size': os.path.getsize(full_path),
                'lastmodified': os.path.getmtime(full_path)
            }

            output += dir_html

        for url_path, fn, full_path in files:
            file_html = self.row_tpl % {
                'type': 'folder',
                'url_path': url_path,
                'fn': fn,
                'size': os.path.getsize(full_path),
                'lastmodified': os.path.getmtime(full_path)
            }

            output += file_html

        output += self.html_table_end
        output += self.html_end

        return output

