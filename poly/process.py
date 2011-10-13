from subprocess import Popen, PIPE
from collections import deque
from threading import Thread
import sys
import os
import time
import select

DEBUG = False
DEBUG_COLOR = False

# used for debug output
VTRED =    '\x1b[31;1m'
VTGREEN =  '\x1b[32;1m'
VTCLEAR =  '\x1b[0m'

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
                if DEBUG:
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
            print('RID: {0}'.format(rid))
            if self.response_handlers.has_key(rid):
                handlers = self.response_handlers.pop(rid)
                print('Handlers: {0}'.format(handlers))
                for h in handlers:
                    h(packet.copy())
            else:
                print('RID has no handlers!')
                print(self.response_handlers)
                
    def run(self):
        packet = self.read_packet()
        packet.popcode('H')
        print('Running Poly/ML, protocol version: ' + packet.popstr())
        packet.popcode('h')
        
        while self.listen:
            try:
                print('Reading off excess...')
                self.read_until_esc() # read off any non-protocol output
                print('Reading packet...')
                packet = self.read_packet(expect_esc=False)
                # TODO: locking
                print('Dispatching...')
                self.dispatch_packet(packet)
            except ListenerKilled:
                print('Listener killed')
                break


class PolyProcess:
    def __init__(self, poly_bin):
        self.request_id = 0
        
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
            print('Closing Poly/ML')
            if self.is_alive(): self.kill()
            
    def write(self, s):
        self.pipe.stdin.write(s)

    def is_alive(self):
        return (self.pipe.poll() == None)
        
    def kill(self):
        self.pipe.terminate()

    def send_request(self, code, args):
        request_string = '\x1b{0}{1}\x1b,{2}\x1b{3}'.format(
            code.upper(), self.request_id,
            '\x1b,'.join([str(x) for x in args]), code.lower())
        self.write(request_string)
        self.request_id += 1
        return (self.request_id - 1)
        
    def add_handler(self, rid, h):
        self.listener.add_handler(rid, h)

