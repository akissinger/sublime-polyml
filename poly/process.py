from subprocess import Popen, PIPE
from collections import deque
import threading
from threading import Thread
import sys
import os
import time
import select

DEBUG_WARN = 1
DEBUG_INFO = 2
DEBUG_FINE = 3
DEBUG_FINEST = 4

DEBUG_LEVEL = 1
DEBUG_COLOR = False

# used for debug output
VTRED =    '\x1b[31;1m'
VTGREEN =  '\x1b[32;1m'
VTCLEAR =  '\x1b[0m'

def debug(s, level = DEBUG_INFO):
    if DEBUG_LEVEL >= level:
        print(s)

def set_debug_level(level):
    DEBUG_LEVEL = level

class ProtocolError(Exception):
    pass

class ListenerKilled(Exception):
    pass

class EscCode:
    def __init__(self, code):
        self.code = code

    def __repr__(self):
        return 'ESC[' + self.code + ']'

class Packet:
    def __init__(self, initial=[]):
        self.tokens = deque(initial)

    def copy(self):
        return Packet(self.tokens)

    def append(self, token):
        self.tokens.append(token)

    def is_response(self):
        # M is currently unimplemented, as it doesn't provide a request-id
        if self.tokens[0].__class__ == EscCode:
            return (self.tokens[0].code == 'R' or
                    self.tokens[0].code == 'I' or
                    self.tokens[0].code == 'V' or
                    self.tokens[0].code == 'O' or
                    self.tokens[0].code == 'T')
        else:
            raise ProtocolError("Malformed packet.")

    def pop(self):
        return self.tokens.popleft()

    def popint(self):
        val = self.tokens.popleft()
        try:
            if val.__class__ == EscCode:
                raise ValueError()
            intval = int(val)
            return intval
        except ValueError:
            raise ProtocolError("Expected int, got: {0}".format(repr(val)))

    def popstr(self):
        val = self.tokens.popleft()
        if (val.__class__ != EscCode):
            return val
        else:
            raise ProtocolError("Expected string, got: {0}".format(repr(val)))

    def popcode(self, code=None):
        val = self.tokens.popleft()
        if code == None:
            if val.__class__ == EscCode:
                return val
            else:
                raise ProtocolError("Expected code, got: {0}".format(repr(val)))
        else:
            if (val.__class__ == EscCode and val.code == code):
                return val
            else:
                raise ProtocolError("Expected code '{0}', got: {1}".format(code, repr(val)))


    def popempty(self):
        val = self.tokens.popleft()
        if (val != ''):
            raise ProtocolError("Expected '', got {0}".format(repr(val)))

    def popuntilcode(self, code):
        while len(self.tokens) != 0:
            val = self.pop()
            if (val.__class__ == EscCode and val.code == code):
                break

class PacketListener(Thread):
    def __init__(self, poly_pipe):
        Thread.__init__(self)
        self.input = poly_pipe.stdout
        #self.pipe = poly_pipe
        self.response_handlers = {}
        self.listen = True

    def kill(self):
        self.listen = False

    def read1(self):
        c = None
        while self.listen:
            stream = select.select([self.input],[],[],0.1)[0]
            if len(stream) == 1:
                c = self.input.read(1)
                if DEBUG_LEVEL >= DEBUG_FINEST:
                    if DEBUG_COLOR: sys.stdout.write(VTRED)
                    sys.stdout.write('['+c+']' if c!='\x1b' else '[ESC]')
                    if DEBUG_COLOR: sys.stdout.write(VTCLEAR)
                break
        if c == '': self.kill() # empty string means we hit EOF
        if self.listen == False: raise ListenerKilled()
        return c

    def read_until_esc(self):
        c = self.read1()
        while (c != '\x1b'):
            #sys.stdout.write(c)
            c = self.read1()

    def read_packet(self, expect_esc=True):
        packet = Packet()
        escape = False
        c = self.read1()
        if expect_esc:
            if c != '\x1b': raise ProtocolError("Expected [ESC], got: '{0}'".format(c))
            code = self.read1()
        else:
            code = c

        packet.append(EscCode(code))
        buf = ''

        c = self.read1()
        while True:
            if escape:  # previous character was an escape
                packet.append(buf)
                buf = ''
                packet.append(EscCode(c))
                if c == code.lower(): break
                escape = False
            else:
                buf += c

            c = self.read1()
            if c == '\x1b':
                escape = True
                c = self.read1()

        return packet

    def add_handler(self, rid, h):
        if not self.response_handlers.has_key(rid):
            self.response_handlers[rid] = []
        self.response_handlers[rid].append(h)

    def dispatch_packet(self, packet):
        if packet.is_response():
            rid = int(packet.tokens[1])
            debug('RID: {0}'.format(rid), DEBUG_FINE)
            if self.response_handlers.has_key(rid):
                handlers = self.response_handlers.pop(rid)
                debug('Handlers: {0}'.format(handlers), DEBUG_FINE)
                for h in handlers:
                    h(packet.copy())
            else:
                debug('RID has no handlers!', DEBUG_WARN)
                debug(self.response_handlers)

    def run(self):
        packet = self.read_packet()
        packet.popcode('H')
        debug('Running Poly/ML, protocol version: ' + packet.popstr(), DEBUG_INFO)
        packet.popcode('h')

        while self.listen:
            try:
                debug('Reading off excess...', DEBUG_FINE)
                self.read_until_esc() # read off any non-protocol output
                debug('Reading packet...', DEBUG_FINE)
                packet = self.read_packet(expect_esc=False)
                # TODO: locking
                debug('Dispatching...', DEBUG_FINE)
                self.dispatch_packet(packet)
            except ListenerKilled:
                debug('Listener killed', DEBUG_INFO)
                break


class PolyProcess:
    def __init__(self, poly_bin):
        self.request_id = 0
        debug ("executing '%s'" % poly_bin, DEBUG_INFO)

        try:
            self.pipe = Popen([poly_bin, "--ideprotocol"],
                stdin=PIPE, stdout=PIPE, stderr=PIPE)
        except OSError:
            raise ProtocolError('Could not run Poly/ML')
            return None

        self.listener = PacketListener(self.pipe)
        self.listener.start()

    def __del__(self):
        if self.pipe != None:
            self.listener.kill()
            debug('Closing Poly/ML', DEBUG_INFO)
            if self.is_alive(): self.kill()

    def write(self, s):
        self.pipe.stdin.write(s)

    def is_alive(self):
        return (self.pipe.poll() == None)

    def kill(self):
        self.pipe.terminate()

    # send a synchronous request with a given timeout
    # returns None on timeout
    def sync_request(self, code, args, timeout=2):
        packet_ready = threading.Condition()
        packet = []

        def h(p):
            debug("handler called", DEBUG_FINE)
            debug(repr(p), DEBUG_FINE)

            packet_ready.acquire()
            packet.append(p)
            packet_ready.notify()
            packet_ready.release()

        packet_ready.acquire()
        rid = self.send_request(code, args, h)
        packet_ready.wait(timeout)
        packet_ready.release()

        debug("returning packet", DEBUG_FINE)
        if len(packet) == 1:
            return packet[0]
        else:
            return None

    # handler is either a handler or a list of handlers
    def send_request(self, code, args, handler = None):
        request_string = '\x1b{0}{1}\x1b,{2}\x1b{3}'.format(
            code.upper(), self.request_id,
            '\x1b,'.join([str(x) for x in args]), code.lower())
        if handler:
            if hasattr(handler, '__call__'):
                self.add_handler(self.request_id, handler)
            else:
                for h in handler:
                    self.add_handler(self.request_id, h)
        self.write(request_string)
        self.request_id += 1
        return (self.request_id - 1)

    def add_handler(self, rid, h):
        self.listener.add_handler(rid, h)

