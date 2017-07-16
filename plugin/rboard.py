import vim
from rb_interface import get_interface

_rboard_url = vim.vars.get('rboardurl', 'http://demo.reviewboard.org')
_pluginname = 'rboard'
_buffer_keybindings = {
    'reviews-list': {
        '<Enter>': 'ViewRequest()',
        'l': 'ViewRequest()',
        'v': 'ViewRequest()',
        'j': 'MoveDown("reviews-list")',
        'm': 'LoadMore("")',
        'G': 'LoadMore("1")',
        },
    'reviews-request': {
        '<Enter>': 'LoadDiff()',
        '<Esc>': 'TabClose()',
        'q': 'TabClose()',
        'R': 'ViewDraftReview()',
        },
    'diff': {
        '<Esc>': 'TabClose()',
        'q': 'TabClose()',
        ('v','c'): 'MakeComment()',
        ('n','c'): 'MakeComment()',
        'R': 'ViewDraftReview()',
        },
    'diff-comment': {
        'y': 'SaveComment()',
        'n': 'TabClose()',
        'q': 'TabClose()',
        },
    'review-draft': {
        '<Esc>': 'TabClose()',
        'q': 'TabClose()',
        'b': 'EditBody("h")',
        'B': 'EditBody("H")',
        'y': 'SubmitReview()',
        }
    }

# vim utilitity interaction
###########################

def set_tabvar(key, value):
    vim.command('let t:%s = ["%s", "%s"]' % (
        key, value.__class__.__name__, value))


def get_tabvar(key):
    obj_type, obj_value = vim.eval('t:%s' % key)
    obj = {'int': int,
           'float': float,
           'str': str,
           'list': eval,
           'dict': eval,
           'tuple': eval}.get(obj_type)(obj_value)
    return obj


def current_lineval():
    return int(vim.eval('line(".")'))


def vim_range():
    sline, _ = vim.current.buffer.mark('<')
    eline, _ = vim.current.buffer.mark('>')
    return sline, eline


def create_buffer(
        buffertype, cmd='tabnew', fname=None, extra_bindings=None,
        tvariables=None, contents=None, no_title=False,
        post_commands=None, readonly=False):
    """create a new buffer."""
    vim.command('%s %s' % (cmd, (fname or buffertype)))
    vim.command('set modifiable')  # this will be unset later if needed
    vim.command('silent! file %s' % (fname or buffertype))
    vim.command('setlocal nonumber')
    vim.command('setlocal norelativenumber')
    vim.command('setlocal buftype=nofile bufhidden=hide')
    vim.command('keepjumps 0d')

    # set mappings
    vim.command('nmapclear <buffer>')

    keybindings = _buffer_keybindings.get(buffertype, {})

    if extra_bindings:
        keybindings.update(extra_bindings)

    for key, command in keybindings.items():
        if isinstance(key, tuple):
            vim.command('%snoremap <buffer> %s :call <SID>%s<CR>' % (
                key[0], key[1], command))
        else:
            vim.command('nnoremap <buffer> %s :call <SID>%s<CR>' % (
                key, command))

    # add tab variables
    if tvariables:
        for k, v in tvariables.items():
            set_tabvar(k, v)

    contents = contents or []

    # add line contents
    if not no_title:
        contents.insert(0, '*%s*  %s' % (buffertype, ' '*80))

    vim.current.buffer[:] = contents

    for command in (post_commands or []):
        vim.command(command)

    if readonly:
        vim.command('set readonly')
        vim.command('set nomodifiable')

    vim.command('set syntax=%s-%s' % (_pluginname, buffertype))
    vim.command('set filetype=%s-%s' % (_pluginname, buffertype))


# actions methods called by vim bindings
########################################


def action_view_diff():
    """Aciton view a diff."""
    interface = get_interface()

    # get the filepath from the current line
    filepath_key = vim.current.line.split()[0]

    # get the recorded uri from the tab variable file_keys
    file_keys = get_tabvar('file_keys')
    filediff_id = file_keys.get(filepath_key, 'none')
    review_request_id = get_tabvar('review_request_id')
    revision = get_tabvar('diff_revision')

    # get the file obj
    file_fields = dict(
            review_request_id=review_request_id,
            diff_revision=revision,
            filediff_id=filediff_id)

    dst = 'DST-%s' % interface.get_file_dst(**file_fields)
    dst = 'SRC-%s' % interface.get_file_src(**file_fields)

    tab_buffers = [src, dst]
    updates = interface.get_filediff_data(
            review_request_id=review_request_id,
            diff_revision=revision,
            filediff_id=filediff_id)

    dst_lines = interface.get_dst_lines(
            review_request_id=review_request_id,
            diff_revision=revision,
            filediff_id=filediff_id)

    tvariables = {
            'tab_buffers': tab_buffers,
            'lineno_converter': updates['dest_global_pos'],
            'review_request_id': review_request_id,
            'diff_revision': revision,
            'filediff_id': filediff_id}

    create_buffer(
            'diff', fname=dst, tvariables=tvariables,
            contents=dst_lines, no_title=True,
            post_commands=['ALEDisable'])

    src_lines = interface.get_src_lines(
            review_request_id=review_request_id,
            diff_revision=revision,
            filediff_id=filediff_id)

    if not src_lines:
        return

    tvariables = dict(tvariables)
    tvariables['lineno_converter'] = updates['source_global_pos']

    create_buffer(
            'diff', cmd='silent! vert diffsplit',
            fname=src, tvariables=tvariables,
            contents=src_lines, no_title=True,
            post_commands=['ALEDisable'])


def action_view_request():
    """View a review request."""
    interface = get_interface()
    review_request_id = vim.current.line.strip().split(' ')[0]

    print "Loading review request %s." % review_request_id
    review_request = interface.get_review_request(
            review_request_id=review_request_id)

    # create lines of contents
    contents = []
    for key in ('changenum', 'summary', 'description'):
        for idx, line in enumerate(
                str(review_request.rsp['review_request'][key] or '').splitlines()):
            if idx:
                contents.append("     %s" % (line))
            else:
                contents.append("# %s : %s" % (key, line))
    diffs = review_request.get_diffs()

    tvariables = None

    if diffs.rsp['total_results']:

        contents.append('')
        contents.append('')
        contents.append('# files :')

        diff = diffs[-1]
        file_keys = {}
        for f in diff.get_files():
            contents.append(f.rsp['dest_file'])
            file_keys[f.rsp['dest_file']] = f.rsp['id']

        tvariables = {
                'file_keys': file_keys,
                'review_request_id': review_request_id,
                'diff_revision': diff['revision'],
                }

    create_buffer(
            'reviews-request',
            fname='review-request-%s' % review_request_id,
            tvariables=tvariables, contents=contents,
            readonly=True)


def action_move_down(buffertype):
    """Move down or load more."""
    if current_lineval() < len(vim.current.buffer[:]):
        vim.command("normal! j")
    else:
        if buffertype == 'reviews-list':
            action_load_more_reviews()


def action_make_comment():

    def num_converter(lineno):
        lineno_converter = get_tabvar('lineno_converter')
        reverse_conv = dict((v, k) for k, v in lineno_converter.items())
        if not reverse_conv:
            return lineno
        orig_lineno = lineno
        add = 0
        while lineno not in reverse_conv:
            add += 1
            lineno -= 1
        return reverse_conv[lineno] + add

    start, end = vim_range()
    start, end = num_converter(start), num_converter(end)

    review_request_id = get_tabvar('review_request_id')
    revision = get_tabvar('diff_revision')
    filediff_id = get_tabvar('filediff_id')

    interface = get_interface()
    request_draft = interface.make_review(review_request_id)

    tvars = {'review_request_id': review_request_id,
             'start': start,
             'filediff_id': filediff_id,
             'num_lines': (end - start + 1)}
    lines = ['# diff comments', '']
    diff_fname = 'diff-comment-%s-%s' % (
            review_request_id, filediff_id)
    create_buffer('diff-comment',
            cmd='silent! tabnew',
            contents=lines, fname=diff_fname,
            tvariables=tvars)


def action_save_comment():
    """Action save comment."""
    review_request_id = get_tabvar('review_request_id')
    start = get_tabvar('start')
    num_lines = get_tabvar('num_lines')
    filediff_id = get_tabvar('filediff_id')
    comment_string = '\n'.join(vim.current.buffer[:])

    interface = get_interface()
    interface.make_comment(
            review_request_id=review_request_id,
            first_line=start,
            text=comment_string,
            filediff_id=filediff_id,
            num_lines=num_lines)
    vim.command('bdelete!')


def action_view_draft_review():
    """View a draft review."""
    interface = get_interface()
    review_request_id = get_tabvar('review_request_id')
    review_draft = interface.make_review(review_request_id)
    lines = []
    lines.append('# header :')
    lines.extend(review_draft['body_top'].splitlines())
    lines.append('')
    lines.append('')

    diff_comments = review_draft.get_diff_comments()
    if len(diff_comments):
        lines.append('# diffs :')

    for diff_comment in diff_comments:
        title = diff_comment.rsp['links']['filediff']['title'].split()[0]
        start = diff_comment.rsp['first_line']
        end = diff_comment.rsp['num_lines'] + start
        comment = diff_comment.rsp['text']
        lines.append("- %s [%s-%s] -" % (title, start, end))
        lines.extend(comment.splitlines())
        lines.append('')

    if review_draft['body_bottom']:
        lines.append('# tail :')
        lines.extend(review_draft['body_bottom'].splitlines())
        lines.append('')
        lines.append('')

    create_buffer('review-draft',
            contents=lines, fname='review-draft-%s' % review_request_id,
            tvariables={'review_request_id': review_request_id},
            readonly=True)


def action_edit_body(body_type):
    """Set up buffer to enter new body description."""
    body_type = {'h':'body_top', 'H':'body_bottom'}.get(body_type)
    review_request_id = get_tabvar('review_request_id')
    interface = get_interface()
    request_draft = interface.make_review(review_request_id)
    lines = []
    lines.append('# add or update body description after this line.')
    lines.extend(request_draft[body_type].splitlines() or [''])
    extra_bindings = {('n', 'y'): 'SaveBody("%s")' % body_type}
    create_buffer(
            'edit-header', fname='edit-body-%s' % review_request_id,
            contents=lines, no_title=True,
            extra_bindings=extra_bindings, tvariables={
                'review_request_id': review_request_id})



def action_save_body(body_type):
    """Save body description."""
    review_request_id = get_tabvar('review_request_id')
    interface = get_interface()
    request_draft = interface.make_review(review_request_id)
    body = '\n'.join(
            [line for line in vim.current.buffer
             if not line.startswith('#')])
    if body_type == 'body_top':
        request_draft.update(body_top=body)
    else:
        request_draft.update(body_bottom=body)
    vim.command('bdelete!')
    print 'updating review body.'


def action_submit_review():
    """Submit or mark the review as public."""
    review_request_id = get_tabvar('review_request_id')
    interface = get_interface()
    request_draft = interface.make_review(review_request_id)
    request_draft.update(public=True)
    vim.command('bdelete!')
    print 'submitting review.'


def action_load_reviews():
    """Load reviews."""
    create_buffer('reviews-list', cmd='edit')
    action_load_more_reviews()
    vim.command('set cursorline')


def action_load_more_reviews(move_down=False):
    """Load more reviews."""
    print 'loading more requests.'
    interface = get_interface(_rboard_url)
    review_requests = interface.get_review_requests(current_lineval())
    current_buffer = vim.current.buffer
    for review_request in review_requests:
        changenum = review_request['changenum']
        changenum = changenum and ('[%s]' % changenum) or ''
        summary = ' '.join(review_request['summary'].splitlines())
        line = "%07s %07s %12s  --  %s" % (
            review_request['id'],
            review_request['status'],
            review_request.links['submitter']['title'],
            (summary + changenum)[:140])
        current_buffer.append(line)
    if int(move_down) == 1:
        vim.command('silent! norm! G')


def action_kill_tab():
    """Delete all buffers in a tab or just the current one."""
    try:
        tab_buffers = get_tabvar('tab_buffers')
        for bufname in tab_buffers:
            vim.command('silent! bdelete %s' % bufname)
    except vim.error:
        vim.command('bdelete!')
