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

function! PolymlDescribeSymbol()
    if !exists('g:poly_bin')
        let g:poly_bin = 'poly'
    endif
python <<EOP
def poly_describe_symbol():
    path = vim.current.buffer.name
    if not path:
        print('You must save the file first')
        return
    lines = vim.current.buffer[:]
    row,col = vim.current.window.cursor
    line_start_pos = 0
    for i in range(row-1):
        line_start_pos += len(lines[i]) + 1
    print("row = {0}, line_start_pos = {1}".format(row, line_start_pos))
    poly_bin = vim.eval('g:poly_bin')
    poly_inst = poly.global_instance(poly_bin)
    if not poly_inst.has_built(path):
        result = poly_do_compile(path, "\n".join(lines))[0]
        if result != 'S':
            print('Failed to compile')
            return
    print('Getting node at position {0}'.format(line_start_pos + col))
    node = poly_inst.node_for_position(path, line_start_pos + col)
    if node:
        name_start = node.start - line_start_pos
        name_end = node.end - line_start_pos
        print('From {0} to {1}'.format(name_start, name_end))
        name = lines[row-1][name_start:name_end]
        ml_type = poly_inst.type_for_node(node)
        if ml_type:
            print('val {0} : {1}'.format(name, ml_type))
        else:
            print('{0} has no type'.format(name))
    else:
        print('Request timed out')
poly_describe_symbol()
EOP
endfunction

au VimLeave * python poly.kill_global_instance()

" vim:sts=4:sw=4:et
