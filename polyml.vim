" Poly/ML integration
" Maintainer:   Alex Merry <dev@randomguy3.me.uk>
" Last Change:  2012 Jun 18
" Version:      0.1
" Contributors:
"
" Usage:
"   Run :Polyml to compile the current file (no need to save first, although
"   QuickFix lists don't work well with unnamed files).
"
"   Auto-opening the QuickFix window on errors can be disabled with
"
"       let g:polyml_cwindow = 0
"

if !has('python')
    echo "Error: Required vim compiled with +python"
    finish
endif

if !exists('g:polyml_cwindow')
    let g:polyml_cwindow = 1
endif

if exists(':Polyml') != 2
    command Polyml :call Polyml()
endif

python <<EOP
import vim
import os
sys.path.append(os.path.dirname(vim.eval('expand("<sfile>")')))
import poly

# The main reason this is a function is to scope poly_inst properly.
# Otherwise, the Poly object won't be garbage collected, and vim will
# hang at exit waiting for the various Python threads to return.
def poly_do_compile(path, ml):
    poly_bin = vim.eval('g:poly_bin')
    poly_inst = poly.global_instance(poly_bin)

    print('Compiling code with Poly/ML...')
    preamble = ''
    if (path):
        working_dir = os.path.dirname(path)
        file_name = os.path.basename(path)
        preamble = "OS.FileSys.chDir \"" + working_dir + "\";\n"
        polysave = working_dir + "/.polysave/" + file_name + ".save"
        
        if os.path.exists(polysave):
            preamble += "PolyML.SaveState.loadState(\"" + polysave + "\");\n"
            preamble += "PolyML.fullGC ();\n"
    else:
        path = '--scratch--'

    return poly_inst.compile_sync(path, preamble, ml)

def rowcol(lines,offset):
    i = 0
    while (i < len(lines) and offset > len(lines[i])):
        offset -= len(lines[i]) + 1
        i += 1
    return i,offset
EOP

function! Polyml()
    if !exists('g:poly_bin')
        let g:poly_bin = 'poly'
    endif
    let l:output = []
    let l:success = 0
python <<EOP
cb = vim.current.buffer
lines = cb[:]
path = cb.name
(result,messages) = poly_do_compile(path, "\n".join(lines))

if result == 'S':
    vim.command("let l:success = 1")
else:
    vim.command("let l:output = ['{0}']".format(poly.translate_result_code(result)))

    for msg in messages:
        line,start_col = rowcol(lines,msg.start_pos)
        end_col = rowcol(lines,msg.end_pos)[1]
        if msg.file_name == '--scratch--':
            file_name = ''
        else:
            file_name = os.path.basename(msg.file_name)

        vim.command("call add(l:output,'{0}:{1}:{2}-{3}: {4}')".format(
            file_name,
            line + 1,
            start_col + 1,
            end_col + 1,
            msg.text.rstrip().replace("'","''")))

EOP

    if l:success
        echo 'Success!'
        silent cexpr! ['Success']
        if g:polyml_cwindow
            cclose
        endif
    else
        " Vim uses the global errorformat for cexpr, not the local one
        let l:efm_save = &g:errorformat
        " the second part matches results from unnamed buffers, but in
        " this case vim cannot jump to the correct position in the file
        setglobal errorformat=%f:%l:%c-%*[0-9]:\ %m,:%l:%c-%*[0-9]:\ %m
        silent cexpr! l:output
        let &g:errorformat = l:efm_save

        if g:polyml_cwindow
            copen
        endif
    endif

endfunction

au VimLeave * python poly.kill_global_instance()


" vim:sts=4:sw=4:et
