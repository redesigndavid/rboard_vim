from rbtools.api.client import RBClient
import rbtools.api.errors as rberrors
from HTMLParser import HTMLParser

_html_parser = HTMLParser()
_interface = None
_p4_conn = None


def get_p4_conn():
    global _p4_conn
    import P4
    if not _p4_conn:
        _p4_conn = P4.P4()
    if not _p4_conn.connected():
        _p4_conn.connect()
    return _p4_conn


def get_p4_file(p4filepath):
    p4conn = get_p4_conn()
    lines = p4conn.run_print(p4filepath)[1].splitlines()
    return lines


def authentication_wrapper(function):

    def wrapped_function(self, *args, **kwargs):
        try:
            return function(self, *args, **kwargs)
        except rberrors.AuthorizationError:
            import vim
            self.login(
                    vim.eval('input("login:")'),
                    vim.eval('inputsecret("password:")'))
            return function(self, *args, **kwargs)

    return wrapped_function


class RBInterface():
    def __init__(self, url):
        self.client = RBClient(url)
        self.root = self.client.get_root()
        try:
            self._version = float(self.root.rsp['product']['version'].split()[0])
        except:
            self._version = 0.0
        self._templates = self.root.rsp['uri_templates']
        self._files = {}
        self._file_data = {}
        self._simplefile_data = {}

    @authentication_wrapper
    def get_review_requests(self, current_line):
        return self.root.get_review_requests(start=current_line)

    @authentication_wrapper
    def get_review_request(self, review_request_id):
        review_request_template = self._templates['review_request']
        url = review_request_template.format(
                review_request_id=review_request_id)
        return self.client.get_url(url)

    @authentication_wrapper
    def get_file_src(self, review_request_id, diff_revision, filediff_id):
        url = self._templates['diff'].format(
                review_request_id=review_request_id,
                diff_revision=diff_revision)
        if url not in self._simplefile_data:
            diff_obj = self.client.get_url(url)
            self._simplefile_data[url] = diff_obj
        diff_obj = self._simplefile_data[url]
        for filesimple in diff_obj.get_files():
            if filesimple['id'] == filediff_id:
                return filesimple['source_file']

    @authentication_wrapper
    def get_file_dst(self, review_request_id, diff_revision, filediff_id):
        url = self._templates['diff'].format(
                review_request_id=review_request_id,
                diff_revision=diff_revision)
        if url not in self._simplefile_data:
            diff_obj = self.client.get_url(url)
            self._simplefile_data[url] = diff_obj
        diff_obj = self._simplefile_data[url]
        for filesimple in diff_obj.get_files():
            if filesimple['id'] == filediff_id:
                return filesimple['dest_file']

    @authentication_wrapper
    def get_file(self, review_request_id, diff_revision, filediff_id):
        url = self._templates['file'].format(
                review_request_id=review_request_id,
                diff_revision=diff_revision,
                filediff_id=filediff_id)

        if url in self._files:
            return self._files[url]

        file_obj = self.client.get_url(url)
        self._files[url] = file_obj
        return self._files[url]

    def get_dst_lines(self, review_request_id, diff_revision, filediff_id):
        if self._version >= 3.0:
            file_obj = self.get_file(review_request_id, diff_revision, filediff_id)
            return file_obj.get_patched_file()['data'].splitlines()

        dest_file = self.get_file_dst(review_request_id, diff_revision, filediff_id)
        updates = self.get_filediff_data(review_request_id, diff_revision, filediff_id)
        dst_updates = updates['dst_updates']
        dst_lines = get_p4_file(dest_file) 
        for lineno, linevalue in dst_updates.iteritems():
            dst_lines[lineno] = linevalue
        return dst_lines

    def get_src_lines(self, review_request_id, diff_revision, filediff_id):
        try:
            if self._version >= 3.0:
                file_obj = self.get_file(review_request_id, diff_revision, filediff_id)
                return file_obj.get_original_file()['data'].splitlines()
            source_file = self.get_file_src(review_request_id, diff_revision, filediff_id)
            return get_p4_file(source_file)
        except:
            return None

    @authentication_wrapper
    def get_filediff_data(self, review_request_id, diff_revision, filediff_id):

        url = self._templates['file'].format(
                review_request_id=review_request_id,
                diff_revision=diff_revision,
                filediff_id=filediff_id)
        if url in self._file_data:
            return self._file_data[url]

        file_obj = self.get_file(review_request_id, diff_revision, filediff_id)

        # chunks are collected differently
        if self._version >= 3.0:
            chunks = file_obj.get_diff_data()['chunks']
        else:
            chunks = file_obj['chunks']

        source_line_global_pos = {}
        dest_line_global_pos = {}
        dst_updates = {}
        for chunk in chunks:
            for line in chunk['lines']:
                try:
                    source_line_global_pos[int(line[1]) - 1] = int(line[0]) - 1
                    dest_line_global_pos[int(line[4]) - 1] = int(line[0]) - 1
                    dst_updates[line[1] - 1] = _html_parser.unescape(line[5])
                except:
                    pass

        self._file_data[url] = {
            'source_global_pos': source_line_global_pos,
            'dest_global_pos': dest_line_global_pos,
            'dst_updates': dst_updates}

        return self._file_data[url]

    @authentication_wrapper
    def make_review(self, review_request_id):
        review_request = self.get_review_request(review_request_id)
        try:
            return review_request.get_reviews().get_review_draft()
        except:
            return review_request.get_reviews().create()

    @authentication_wrapper
    def make_comment(
            self, review_request_id, first_line,
            text, filediff_id, num_lines):
        request = self.make_review(review_request_id)
        request.get_diff_comments().create(
                first_line=first_line,
                text=text,
                filediff_id=filediff_id,
                num_lines=num_lines)

    def login(self, user, password):
        self.client.login(user, password)


def get_interface(url=None):
    global _interface
    if not _interface:
        _interface = RBInterface(url)
    return _interface
