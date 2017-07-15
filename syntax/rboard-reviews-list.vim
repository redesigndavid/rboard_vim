syntax region rblistnumbers start='^\s\+' end='\s'
syntax match rbdoubledash +--+
syntax region rboardtitle     start='*' end='*'

highlight link rblistnumbers MoreMsg 
highlight link rbdoubledash MoreMsg 
highlight rboardtitle cterm=NONE ctermbg=darkgreen ctermfg=white
highlight CursorLine cterm=NONE ctermbg=green ctermfg=white
