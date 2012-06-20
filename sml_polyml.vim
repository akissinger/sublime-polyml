" Poly/ML integration
" Maintainer:   Alex Merry <dev@randomguy3.me.uk>
" Last Change:  2012 Jun 19
" Version:      0.1
" Contributors:
"
" Installation:
"   Drop sml_polyml.vim and the poly/ directory into ~/.vim/ftplugin
"
" Usage:
"   :Polyml [timeout]
"   Compile the current file. There is no need to save first, although
"   QuickFix lists don't work well with unnamed buffers.  The timeout is
"   in seconds.
"
"   Auto-opening the QuickFix window on errors can be disabled with
"       let g:polyml_cwindow = 0
"
"
"   :PolymlGetType
"   Gets the type of the expression under the cursor.  If you have edited the
"   file since the last compile, you should re-compile it with :Polyml first.
"
"
"   :[range]PolymlAccessors
"   Generates accessor declarations for a datatype, as selected by [range].
"   The usual use is to visually highlight (with V) the datatype declaration,
"   and then call :'<,'>PolymlAccessors
"

if !has('python')
    echo "Error: Required vim compiled with +python"
    finish
endif

if !exists('g:polyml_cwindow')
    let g:polyml_cwindow = 1
endif

if !exists('g:polyml_accessor_buffer_name')
    let g:polyml_accessor_buffer_name = '__poly_accessors__'
endif

if exists(':Polyml') != 2
    command -nargs=? Polyml :call Polyml(<args>)
endif

if exists(':PolymlGetType') != 2
    command PolymlGetType :call PolymlGetType()
endif

if exists(':PolymlAccessors') != 2
    command -range=% PolymlAccessors :<line1>,<line2>python PolymlCreateAccessors()
endif

python <<EOP
import vim
import os
sys.path.append(os.path.dirname(vim.eval('expand("<sfile>")')))
import poly

# The main reason this is a function is to scope poly_inst properly.
# Otherwise, the Poly object won't be garbage collected, and vim will
# hang at exit waiting for the various Python threads to return.
def poly_do_compile(path, ml, timeout):
    poly_bin = vim.eval('g:poly_bin')
    poly_inst = poly.global_instance(poly_bin)

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

    return poly_inst.compile_sync(path, preamble, ml, timeout)

def rowcol(lines,offset):
    i = 0
    while (i < len(lines) and offset > len(lines[i])):
        offset -= len(lines[i]) + 1
        i += 1
    return i,offset

def poly_get_type():
    path = vim.current.buffer.name
    if not path:
        vim.command('echo "You must save and compile the file first!"')
        return
    lines = vim.current.buffer[:]
    row,col = vim.current.window.cursor
    line_start_pos = 0
    for i in range(row-1):
        line_start_pos += len(lines[i]) + 1
    poly_bin = vim.eval('g:poly_bin')
    poly_inst = poly.global_instance(poly_bin)
    if not poly_inst.has_built(path):
        vim.command('echo "You must compile the file first!"')
        return
    try:
        node = poly_inst.node_for_position(path, line_start_pos + col)
        if node:
            ml_type = poly_inst.type_for_node(node)
            name_start = node.start - line_start_pos
            name_end = node.end - line_start_pos
            if (name_start < 0 or name_end > len(lines[row-1])):
                if ml_type:
                    vim.command('echo "Expression spans multiple lines, and has type {0}"'.format(ml_type.replace("'","''")))
                else:
                    vim.command('echo "Expression spans multiple lines, and has no type"')
            else:
                name = lines[row-1][name_start:name_end]
                if ml_type:
                    vim.command('echo "val {0} : {1}"'.format(name.replace("'","''"), ml_type.replace("'","''")))
                else:
                    vim.command("echo 'Expression \"{0}\" has no type'".format(name.replace("'","''")))
        else:
            vim.command('echo "Failed to find parse tree location"')
    except poly.process.Timeout:
        vim.command('echo "Request timed out"')

def poly_format_message(msg):
        if msg.message_code == 'E':
            mtype = 'Error: '
        elif msg.message_code == 'W':
            mtype = 'Warning: '
        elif msg.message_code == 'X':
            mtype = 'Exception: '
        else:
            mtype = ''

        if not msg.location:
            return mtype + msg.text
        else:
            if msg.location.file_name == '--scratch--':
                file_name = ''
            else:
                file_name = os.path.basename(msg.location.file_name)

            if msg.location.line:
                line = msg.location.line
                start_col = msg.location.start
                end_col = msg.location.end
            else:
                # try to find the right buffer
                bufidx = int(vim.eval("bufnr('{0}')".format(file_name.replace("'","''")))) - 1
                if bufidx >= 0:
                    lines = vim.buffers[bufidx][:]
                else:
                    # guess at the current buffer
                    lines = vim.current.buffer[:]
                line,start_col = rowcol(lines,msg.location.start)
                end_col = rowcol(lines,msg.location.end)[1]

            return "{0}:{1}:{2}-{3}: {5}{4}".format(
                file_name,
                line + 1,
                start_col + 1,
                end_col + 1,
                msg.text,
                mtype)
EOP

function! Polyml(...)
    if !exists('g:poly_bin')
        let g:poly_bin = 'poly'
    endif
    let l:output = []
    let l:success = 0
    let l:timeout = 10
    if a:0 > 0
        let l:timeout = a:000[0]
    endif
    redraw
    echo "Compiling code with Poly/ML..."
python <<EOP

try:
    (result,messages) = poly_do_compile(vim.current.buffer.name,
                                        "\n".join(vim.current.buffer[:]),
                                        int(vim.eval('l:timeout')))

    hr_result = poly.translate_result_code(result)
    vim.command("let l:success = 1")
    vim.command("let l:result = '{0}'".format(hr_result.replace("'","''")))
    vim.command("let l:output = [l:result]".format(hr_result))

    for msg in messages:
        vim.command("call add(l:output,'{0}')".format(
            poly_format_message(msg).replace("'","''")))

    del result
    del messages
except poly.process.Timeout:
    vim.command('echo "Communication with Poly/ML timed out"')
EOP

    if l:success
        redraw
        echo l:result
        " Vim uses the global errorformat for cexpr, not the local one
        let l:efm_save = &g:errorformat
        " the second part matches results from unnamed buffers, but in
        " this case vim cannot jump to the correct position in the file
        setglobal errorformat=%f:%l:%c-%*[0-9]:\ %m,:%l:%c-%*[0-9]:\ %m
        silent cexpr! l:output
        let &g:errorformat = l:efm_save

        if g:polyml_cwindow && len(l:output) > 1
            copen
        else
            cclose
        endif
    else
        redraw
        echo ''
    endif
endfunction

function! PolymlGetType()
    if !exists('g:poly_bin')
        let g:poly_bin = 'poly'
    endif
    python poly_get_type()
endfunction

function! s:get_visual_selection()
    let [lnum1, col1] = getpos("'<")[1:2]
    let [lnum2, col2] = getpos("'>")[1:2]
    let lines = getline(lnum1, lnum2)
    let lines[-1] = lines[-1][: col2 - 2]
    let lines[0] = lines[0][col1 - 1:]
    return join(lines, "\n")
endfunction

function! Poly_get_accessor_buffer()
    let l:scr_bufnum = bufnr(g:polyml_accessor_buffer_name)
    if l:scr_bufnum == -1
        " open a new scratch buffer
        exe "new " . g:polyml_accessor_buffer_name
        let l:scr_bufnum = bufnr(g:polyml_accessor_buffer_name)
    else
        " Scratch buffer is already created. Check whether it is open
        " in one of the windows
        let l:scr_winnum = bufwinnr(l:scr_bufnum)
        if l:scr_winnum != -1
            " Jump to the window which has the scratch buffer if we are not
            " already in that window
            if winnr() != l:scr_winnum
                exe l:scr_winnum . "wincmd w"
            endif
        else
            " Create a new scratch buffer
            exe "split +buffer" . l:scr_bufnum
        endif
    endif
    setlocal buftype=nofile
    setlocal bufhidden=delete
    setlocal noswapfile
    setlocal nobuflisted
    return l:scr_bufnum
endfunction

python <<EOP
def PolymlCreateAccessors():
    if len(vim.current.range) == 0:
        vim.command("echo 'No range given'")
        return
    accessors = poly.accessors.sig_for_record("\n".join(vim.current.range[:]))
    if not accessors:
        vim.command("echo 'Range is not a record'")
        return
    bufidx = int(vim.eval('Poly_get_accessor_buffer()')) - 1
    vim.buffers[bufidx][:] = accessors.split('\n')
EOP

au VimLeave * python poly.kill_global_instance()

map <silent> <F5> :Polyml<CR>

" vim:sts=4:sw=4:et
