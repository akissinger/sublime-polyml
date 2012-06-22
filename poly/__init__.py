from sys import stdout
import time
import process
from process import PolyProcess, ProtocolError, Timeout
import accessors
import console
import gc

"""A library for accessing Poly/ML's IDE integration

Poly/ML provides an IDE interface for compiling and inspecting code.  This
library manages communication an Poly/ML instance using this interface.  It is
intended to be used to build plugins for text editors.

The main class is Poly, which should be instantiated using global_instance().

The accessors module has methods for generating signatures and structs from
datatypes which are indepent from Poly (and hence from Poly/ML).
"""

poly_global = None

def global_instance(poly_bin='poly'):
    """Get the global instance of the Poly class

    poly_bin -- the path to the Poly/ML binary

    If there is no global instance already, one will be created.
    poly_bin is only used in this case, not when the instance
    already exists.

    Returns a Poly object.
    """
    global poly_global
    if poly_global == None:
        poly_global = Poly(poly_bin)
    return poly_global

def kill_global_instance():
    """Discards the global instance of the Poly class

    Obviously, Python is garbage collected, so there is
    no guarantee the instance will not stay around.
    The global reference will be removed, though, and
    a garbage collection run will be forced.
    """
    global poly_global
    if poly_global != None:
        poly_global = None
    gc.collect()

class PolyLocation:
    """A location (range) in a file.

    file_name -- the file the location is in
    start -- the start of the location
    end -- the end offset of the location
    line -- (optional) the line number of the location

    If line is None, start and end are absolute offsets in the file.
    Otherwise, they are relative to the line (FIXME: is this true?)
    """

    def __init__(self, file_name=None, line=None, start=None, end=None):
        self.start = start
        self.end = end
        self.line = line
        self.file_name = file_name

    def __str__(self):
        if self.line:
            return ("line {1} of {0} ({2}-{3})".format(
                self.file_name, self.line, self.start, self.end))
        else:
            return ("{0} ({1}-{2})".format(
                self.file_name, self.start, self.end))

    def __repr__(self):
        return "<PolyLocation: file_name='{1}' line={2} start={3} end={4}>".format(
            self.__class__, self.file_name, self.line, self.start, self.end)

class PolyNode(PolyLocation):
    """A node in a Poly/ML parse tree.

    start -- the starting offset of the node in the ML code
    end -- the ending offset of the node in the ML code
    parse_tree -- the parse tree id
    file_name -- the file name of the parse tree
    commands -- a list of valid commands for the node
    """

    def __init__(self, file_name=None, start=None, end=None,
                 parse_tree=None, commands=[]):
        self.start = start
        self.end = end
        self.line = None
        self.file_name = file_name
        self.parse_tree = parse_tree
        self.commands = commands[:] # shallow copy

    def __repr__(self):
        return "<PolyNode: file_name='{1}' line={2} start={3} end={4} parse_tree={5} commands={6}>".format(
            self.__class__, self.file_name, self.line, self.start,
            self.end, self.parse_tree, self.commands)

class PolyMessage:
    """A message from Poly/ML

    message_code -- 'E' for an error, 'W' for a warning, 'X' for exception,
                    None for other
    text -- the message text
    location -- (optional) location information
    """

    def __init__(self, message_code, text, location=None):
        self.message_code = message_code
        self.text = text
        self.location = location

    def __str__(self):
        if self.message_code == 'E':
            mtype = 'Error: '
        elif self.message_code == 'W':
            mtype = 'Warning: '
        elif self.message_code == 'X':
            mtype = 'Exception: '
        else:
            mtype = ''
        if self.location:
            return "{0}{1}: {2}".format(
                mtype,
                self.location,
                self.text)
        else:
            return "{0}{1}".format(
                mtype,
                self.text)

    def __repr__(self):
        if self.location:
            return "<{0} message_code={1} location={2} text='{3}'>".format(
                self.__class__,
                self.message_code,
                repr(self.location),
                self.text)
        else:
            return "<{0} message_code={1} text='{2}'>".format(
                self.__class__,
                self.message_code,
                self.text)

class PolyException(PolyMessage):
    """A message detailing an exception from Poly/ML"""

    def __init__(self, text, location=None):
        self.message_code = 'X'
        self.text = text
        self.location = location

class PolyErrorMessage(PolyMessage):
    """A message detailing an error (or warning) from Poly/ML"""

    def __init__(self, message_code, file_name, line, start_pos, end_pos, text):
        self.message_code = message_code
        self.location = PolyLocation(file_name, line, start_pos, end_pos)
        self.text = text

class Poly:
    """The core class for interacting with a Poly/ML instance.

    poly_bin -- the path to the Poly/ML binary; only used when creating
                self.process
    process -- the Poly/ML process (lazily created)
    compile_in_progress -- whether there is currently an async compilation
                           happening
    """

    def __init__(self, poly_bin='poly'):
        self.poly_bin = poly_bin
        self.process = None
        self.compile_in_progress = False
        self._parse_trees = {}

        # for _clean_text()
        import re
        self._clean_rexp = re.compile(r"\s+")

    def has_built(self, path):
        """Return whether a file has been compiled."""
        return (path in self._parse_trees.keys())

    def ensure_poly_running(self):
        """Starts the Poly/ML process if it is not already running."""
        if self.process == None or not self.process.is_alive():
            # reset state, in case poly just died
            self.compile_in_progress = False
            self._parse_trees = {}
            self.process = PolyProcess(self.poly_bin)

    def node_for_position(self, path, position):
        """Get the PolyNode at a given position.

        This will return None if the file has not been
        compiled.  The information is only accurate for
        the last successful compile of that file.

        path -- the path of the file, as passed to compile or compile_sync
        position -- a zero-indexed offset in the ml code last passed to
                    compile or compile_sync for path

        returns a PolyNode object, or None
        raises poly.process.Timeout if the request to Poly/ML times out
        raises poly.process.ProtocolError if communication with Poly/ML failed
        """
        if path in self._parse_trees.keys():
            node = PolyNode()
            node.file_name = path
            p = self.process.sync_request('O',
                [self._parse_trees[path], position, position])
            p.popcode('O')
            p.pop() # ignire RID
            p.popcode(',')
            node.parse_tree = p.pop()
            p.popcode(',')
            node.start = p.popint()
            p.popcode(',')
            node.end = p.popint()
            while p.popcode().code == ',':
                node.commands.append(p.popstr())
            return node
        else:
            return None

    def type_for_node(self, node):
        """Get the type of a PolyNode

        This will return None if the node does not have a type.
        The information is only accurate if the file has not been
        recompiled since the PolyNode object was created.

        node -- a PolyNode, as returned by node_for_position or
                declaration_for_node

        returns a string giving the type, or None
        raises poly.process.Timeout if the request to Poly/ML times out
        raises poly.process.ProtocolError if communication with Poly/ML failed
        """
        if node and 'T' in node.commands:
            p = self.process.sync_request('T',
                [node.parse_tree, node.start, node.end])
            p.popcode('T')
            for i in range(7): p.pop() # ignore info about the ident.
            if p.popcode().code == ',':
                return p.popstr().strip()
            else:
                return None
        else:
            return None

    def declaration_for_node(self, node):
        """Get the PolyNode for the declaration of a PolyNode

        This will return None if the node does not have a declaration.
        The information is only accurate if the file has not been
        recompiled since the PolyLocation object was created.

        node -- a PolyNode, as returned by node_for_position

        Returns a PolyLocation for the declaration, or None.
        This may be a PolyNode.

        Due to a shortcoming of Poly/ML, the location filename will not
        include the path to the file (FIXME: need some way to specify
        the search path?)

        raises poly.process.Timeout if the request to Poly/ML times out
        raises poly.process.ProtocolError if communication with Poly/ML failed
        """
        if node and 'I' in node.commands:
            p = self.process.sync_request('I',
                [node.parse_tree, node.start, node.end, 'I'])

            p.popcode('I')
            for i in range(7): p.pop() # ignore info about the ident.
            if p.popcode().code == ',':
                file_name = p.popstr()
                p.popcode(',')
                line = p.popint()
                p.popcode(',')
                start = p.popint()
                p.popcode(',')
                end = p.popint()

                if file_name in self._parse_trees.keys():
                    if line:
                        print('Got line number ({0}) for self-compiled file!'.format(line))
                        return PolyLocation(file_name, line, start, end)
                    else:
                        return PolyNode(file_name, start, end, self._parse_trees[file_name])
                else:
                    return PolyLocation(file_name, line, start, end)

                return dnode
            else:
                return None
        else:
            return None

    def _clean_text(self, text):
        """Removes excess whitespace from a string.

        Returns the given text with all contiguous whitespace replaced by
        a single space, and any whitespace at the start or end removed.

        Poly/ML puts newlines into its messages; this allows us to strip
        them out.
        """
        return self._clean_rexp.sub(' ', text.strip())

    def _pop_compile_result(self, p, file):
        """Reads an R response and returns the result code as a string

        Also saves the parse tree ID in self._parse_trees.

        p -- a poly.process.Packet containing a compilation result block
        file -- the key to use for saving the parse tree ID
        """
        p.popcode('R')  # pop off leading p code
        p.pop() # ignore RID
        p.popcode(',')
        self._parse_trees[file] = p.pop() # save parse tree ID
        p.popcode(',')
        result_code = p.popstr()
        p.popcode(',')
        p.popint()  # ignore final offset
        p.popcode(';')
        p.popempty()  # empty string between escape codes
        return result_code

    def _pop_d_message(self, p):
        """Reads a D message from a Packet

        Returns a pair of PolyLocation and identifier
        """
        p.popcode('D')
        file_name = p.popstr()
        p.popcode(',')
        line = p.popint()
        if not line:
            line = None
        p.popcode(',')
        start = p.popint()
        p.popcode(',')
        end = p.popint()
        p.popcode(';')
        text = p.popstr()
        p.popcode('d')
        return PolyLocation(file_name, line, start, end), text

    def _pop_compile_exception_message(self, p):
        """Reads an exception message from an R response

        p -- a poly.process.Packet containing a compilation result block,
             that has already had _pop_compile_result called on it,
             and had the result 'X'

        Returns a PolyException message
        """
        p.popcode('X')  # pop off leading p code
        exp = PolyException('')
        message = ''
        if not p.nextiscode():
            message = p.popstr()
        code = p.popcode().code
        while code != 'x':
            if code == 'D':
                p.pushcode('D')
                exp.location,text = self._pop_d_message(p)
                if len(message):
                    message += ' '
                message += text
            else:
                p.popuntilcode(code.swapcase())
            if not p.nextiscode():
                if len(message):
                    message += ' '
                n = p.popstr()
                message += n
            code = p.popcode().code
        p.pop_until_nonempty()
        exp.text = self._clean_text(message)
        return exp

    def _pop_compile_error_messages(self, p):
        """Reads the error list from an R response

        p -- a poly.process.Packet containing a compilation result block,
             that has already had _pop_compile_result called on it (and
             _pop_compile_exception_message if the result was 'X')

        Returns a list of PolyErrorMessage objects.
        """
        messages = []
        while p.popcode().code == 'E':
            message_code = p.popstr()
            p.popcode(',')
            file_name = p.popstr()
            p.popcode(',')
            line = p.popint()
            if not line:
                line = None
            p.popcode(',')
            start_pos = p.popint()
            p.popcode(',')
            end_pos = p.popint()

            p.popcode(';')
            text = p.popstr()
            code = p.popcode()

            # FIXME: IDE protocol docs suggest D isn't nested in E
            while code.code != 'e':
                if code.code == 'D':
                    p.popuntilcode(';')
                    text += ' ' + p.popstr().strip() + ' ' # symbol, TODO: mark this up as a link
                    code = p.popcode('d')
                    text += p.popstr().strip() # message text
                    code = p.popcode()

            p.popempty()  # empty string between escape codes

            text = self._clean_text(text)
            messages.append(PolyErrorMessage(message_code, file_name, line, start_pos, end_pos, text))
        return messages

    def _read_compile_response(self, p, file):
        """Parses the response packet for a compilation

        p -- a poly.process.Packet containing a compilation result block
        file -- the file name for the compilation

        Returns a pair of result code (a single-character string) and
        a list of PolyMessage objects.
        """
        result_code = self._pop_compile_result(p, file)
        if result_code == 'X':
            messages = [self._pop_compile_exception_message(p)]
            messages += self._pop_compile_error_messages(p)
        else:
            # FIXME: format for result code 'L' is unclear
            messages = self._pop_compile_error_messages(p)
        return result_code, messages

    def compile_sync(self, file, prelude, source, timeout=10):
        """Sends ML code for compilation, and waits for the result

        file -- the file name for the compilation
        prelude -- ML code to set up the compilation state (eg:
                   loading a saved state)
        source -- the ML code to compile
        timeout -- (optional) how long to wait, in seconds (default: 10)

        Returns a pair of result code (a single-character string) and
        a list of PolyMessage objects.  If the result code is 'X', the
        first will be a PolyException and the remainder PolyErrorMessage
        objects, otherwise they will all be PolyErrorMessage objects.
        """
        if self.compile_in_progress:
            return None,[]

        self.ensure_poly_running()
        p = self.process.sync_request('R',
                                      [file, 0, len(prelude), len(source), prelude, source],
                                      timeout)
        return self._read_compile_response(p, file)


    def compile(self, file, prelude, source, handler):
        """Sends ML code for compilation

        file -- the file name for the compilation
        prelude -- ML code to set up the compilation state (eg:
                   loading a saved state)
        source -- the ML code to compile
        handler -- a method to call when the compilation has finished

        The handler will be passed two arguments: the result code (a
        single-character string) and a list of PolyMessage objects.  If the
        result code is 'X', the first will be a PolyException and the remainder
        PolyErrorMessage objects, otherwise they will all be PolyErrorMessage
        objects.

        Returns the request ID (an integer).
        """
        if self.compile_in_progress:
            return -1

        self.ensure_poly_running()
        self.compile_in_progress = True

        def run_handler(p):
            self.compile_in_progress = False
            result_code,messages = self._read_compile_response(p, file)
            handler(result_code, messages)

        rid = self.process.send_request('R',
                [file, 0, len(prelude), len(source), prelude, source],
                run_handler)

        return rid

    def cancel_compile(self, rid):
        """Cancels a compilation in progress

        rid -- the request id, as returned by compile()
        """
        self.process.send_request('K', [rid])

def translate_result_code(code):
    """Returns a human-readable description of a compilation result code"""
    if code == 'S': return 'Success'
    elif code == 'X': return 'Exception in ML code'
    elif code == 'L': return 'Error or exception in ML prelude'
    elif code == 'F': return 'Parse/typecheck error'
    elif code == 'C': return 'Compilation cancelled'
    else: return "Unknown result code '{0}'".format(code)

def run_tests():
    import threading

    VTRED =    '\x1b[31;1m'
    VTGREEN =  '\x1b[32;1m'
    VTCLEAR =  '\x1b[0m'

    compile_done = threading.Condition()

    def happy_print(msg):
        print(VTGREEN + msg + VTCLEAR)

    def sad_print(msg):
        print(VTRED + '!!! ERROR: ' + msg + VTCLEAR)

    def output_compile_result(type, exp_result_code, result_code, messages):
        if result_code != exp_result_code:
            sad_print(type + ' compile result was "' +
                  translate_result_code(result_code) + '" but expected ' +
                  translate_result_code(exp_result_code) + '"')
        else:
            happy_print(type + ' compile result was "' +
                  translate_result_code(result_code) + '", as expected')
        for msg in messages:
            print('  {0}'.format(msg))

    def test_handler(result_code, messages):
        compile_done.acquire()
        output_compile_result('Async', 'S', result_code, messages)
        compile_done.notify()
        compile_done.release()

    def test_fail_handler(result_code, messages):
        compile_done.acquire()
        output_compile_result('Async', 'F', result_code, messages)
        compile_done.notify()
        compile_done.release()

    process.DEBUG_LEVEL = 2
    process.DEBUG_COLOR = True

    poly = Poly()
    compile_done.acquire()
    poly.compile('-scratch-', '', 'fun p x y = x + y\n', test_handler)
    poly.compile('-scratch-', '', 'fun p x y = x + y\n', test_handler)
    compile_done.wait()
    compile_done.release()

    compile_done.acquire()
    poly.compile('-scratch-', '', 'fun p x y = x + y\n', test_handler)
    compile_done.wait()
    compile_done.release()

    compile_done.acquire()
    poly.compile('-scratch-', '', 'fun p y = x + y\n', test_fail_handler)
    compile_done.wait()
    compile_done.release()

    (result_code, messages) = poly.compile_sync('-scratch-', '', 'fun p x y = x + y\n')
    output_compile_result('Sync', 'S', result_code, messages)

    (result_code, messages) = poly.compile_sync('-scratch-', '', 'fun p y = x + y\n')
    output_compile_result('Sync', 'F', result_code, messages)

    mlcode = """fun p x y = x + y
                val brick = p 1 3
                exception exp of unit;
                val foo = brick;
                raise exp()
             """
    (result_code, messages) = poly.compile_sync('-scratch-', '', mlcode)
    output_compile_result('Sync', 'X', result_code, messages)

    mlcode = "fun p x y = x + y\nval foo = p 1 3\nval bar = foo\n"
    (result_code, messages) = poly.compile_sync('-scratch-', '', mlcode)
    output_compile_result('Sync', 'S', result_code, messages)

    def check_type(node, type, exp_type):
        if type == exp_type:
            happy_print("Node type is '{0}', as expected".format(type))
        else:
            sad_print("Node type is '{0}', expected '{1}'".format(type, exp_type))

    def check_node(node, exp_expr, exp_cmds=[]):
        good = True
        expr = '<not found>'
        if node.file_name != '-scratch-':
            sad_print("Node file_name is '{0}', expected '-scratch'".format(node.file_name))
            good = False
        if node.line != None:
            sad_print("Node line is '{0}', expected None".format(node.line))
            good = False
        if node.start < 0 or node.end > len(mlcode):
            sad_print("Node range ({0}-{1}) is invalid".format(node.start,
                                                               node.end))
            good = False
        else:
            expr = mlcode[node.start:node.end]
            if expr != exp_expr:
                sad_print("Node expressio is '{0}', expected '{1}'".format(
                    expr, exp_expr))
                good = False
        if node.parse_tree != poly._parse_trees['-scratch-']:
            sad_print("Node parse_tree is '{0}', expected '{1}'".format(
                node.parse_tree, poly._parse_trees['-scratch-']))
            good = False
        for c in exp_cmds:
            if not c in node.commands:
                sad_print("Node commands is '{0}', expected it to contain '{1}'".format(
                    node.commands, c))
                good = False
        if good:
            happy_print("Got valid node: {0} ({1})".format(repr(node), expr))
        else:
            sad_print("Got invalid node: {0} ({1})".format(repr(node), expr))

    node = poly.node_for_position('-scratch-', 24)
    check_node(node, 'foo', ['T'])
    type = poly.type_for_node(node)
    check_type(node, type, 'int')

    node = poly.node_for_position('-scratch-', 28)
    check_node(node, 'p', ['T'])
    type = poly.type_for_node(node)
    check_type(node, type, 'int -> int -> int')
    decl_loc = poly.declaration_for_node(node)
    check_node(decl_loc, 'p')

    node = poly.node_for_position('-scratch-', 44)
    check_node(node, 'foo', ['T'])
    type = poly.type_for_node(node)
    check_type(node, type, 'int')
    decl_loc = poly.declaration_for_node(node)
    check_node(decl_loc, 'foo')

    record = """
      datatype T = MatchState of {
        (* names context for fresh names when copying bboxes in pat *)
        names        : int * int,
        (* pattern and target graphs *)
        pat          : string,
        tgt          : string,
        (* internal vertex mapping from pat to tgt *)
        vmap         : int list
      }
    """
    mlcode = """
      fun K x _ = x
      signature OGRAPH_MATCH_STATE
      = sig
        type T
        {0}
      end
      structure OGraphMatchState
      = struct
        {1}

        {2}
      end
    """.format(accessors.sig_for_record(record),
               record,
               accessors.struct_for_record(record))
    (result_code, messages) = poly.compile_sync('-scratch-', '', mlcode)
    output_compile_result('Accessors', 'S', result_code, messages)

if __name__ == '__main__':
    run_tests()


