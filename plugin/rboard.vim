if exists("loaded_rboard_vim")
  finish
endif
let g:loaded_rboard_vim = 1


" --------------------------------
python import sys
python import vim
python sys.path.append(vim.eval('expand("<sfile>:h")'))
python import rboard


" --------------------------------
"  Function(s)
" --------------------------------
function! rboard#InitBoard()
    command LoadReviewBoard call rboard#LoadReviewBoard()
    map <leader>lr :LoadReviewBoard<CR>
endfunction

function! s:MakeComment() range
python rboard.action_make_comment() 
endfunction

function! s:SaveComment() range
python rboard.action_save_comment() 
endfunction

function! s:LoadDiff()
python rboard.action_view_diff() 
endfunction

function! s:TabClose()
python rboard.action_kill_tab() 
endfunction

function! s:ViewRequest()
python rboard.action_view_request() 
endfunction

function! s:MoveDown(arg)
python rboard.action_move_down(vim.eval("a:arg")) 
endfunction

function! s:EditBody(arg)
python rboard.action_edit_body(vim.eval("a:arg")) 
endfunction

function! s:SubmitReview()
python rboard.action_submit_review()
endfunction

function! s:SaveBody(arg)
python rboard.action_save_body(vim.eval("a:arg")) 
endfunction

function! s:ViewDraftReview()
python rboard.action_view_draft_review() 
endfunction

function! s:LoadMore(arg)
python rboard.action_load_more_reviews(vim.eval("a:arg")) 
endfunction


function! rboard#LoadReviewBoard()
python rboard.action_load_reviews() 
endfunction

" --------------------------------
"  Expose our commands to the user
" --------------------------------
call rboard#InitBoard()
