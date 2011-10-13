from sys import stdout
import time

import process
from process import PolyProcess, ProtocolError


class PolyMessage:
    def __init__(self, message_code, filename, start_pos, end_pos, text):
        self.message_code = message_code
        self.filename = filename
        self.start_pos = int(start_pos)
        self.end_pos = int(end_pos)
        self.text = text
        
    def __str__(self):
        return "{0} '{1}' ({2}-{3}): {4}".format(
            'Error' if self.message_code == 'E' else 'Warning',
            self.filename,
            self.start_pos,
            self.end_pos,
            self.text)
    
    def __repr__(self):
        return repr(self.__str__())


class Poly:
    def __init__(self, poly_bin):
        self.request_id = 0
        self.poly_bin = poly_bin
        self.process = None
        self.compile_in_progress = False
    
    def ensure_poly_running(self):
        if self.process == None or not self.process.is_alive():
            self.process = PolyProcess(self.poly_bin)
    
    def compile(self, file, prelude, source, handler):
        if self.compile_in_progress:
            return -1
        
        self.ensure_poly_running()
        self.compile_in_progress = True
        rid = self.process.send_request(
                'R', [file, 0, len(prelude), len(source), prelude, source])
        
        def run_handler(p):
            self.compile_in_progress = False
            p.popcode('R')  # pop off leading p code
            if (p.popint() != rid):
                raise ProtocolError('Bad response ID.')
            p.popcode(',')
            p.pop()  # ignore parse tree id
            p.popcode(',')
            result_code = p.popstr()
            p.popcode(',')
            p.popint()  # ignore final offset
            p.popcode(';')
            p.popempty()  # empty string between escape codes
            
            messages = []
            while p.popcode().code == 'E':
                message_code = p.popstr()
                p.popcode(',')
                filename = p.popstr()
                p.popcode(',')
                p.popint()  # ignore line number, seems wrong anyway
                p.popcode(',')
                start_pos = p.popint()
                p.popcode(',')
                end_pos = p.popint()
                
                p.popcode(';')
                text = p.popstr()
                code = p.popcode()
                
                while code.code != 'e':
                    if code.code == 'D':
                        p.popuntilcode(';')
                        text += p.popstr() # symbol, TODO: mark this up as a link
                        code = p.popcode('d')
                        text += p.popstr() # message text
                        code = p.popcode()
                
                p.popempty()  # empty string between escape codes
                
                messages.append(PolyMessage(message_code, filename, start_pos, end_pos, text))
            
            handler(result_code, messages)
        
        self.process.add_handler(rid, run_handler)
        
        return rid
        
    def cancel_compile(self, rid):
        self.process.send_request('K', [rid])
        

def translate_result_code(code):
        if code == 'S': return 'Success'
        elif code == 'X': return 'Exception in ML code'
        elif code == 'L': return 'Error or exception in ML prelude'
        elif code == 'F': return 'Parse/typecheck error'
        elif code == 'C': return 'Compilation cancelled'


if __name__ == '__main__':
    def test_handler(result_code, messages):
        print(translate_result_code(result_code))
        
        for msg in messages:
            print('{0}:({1}--{2}): {3}\n'.format(msg.filename, msg.start_pos, msg.end_pos, msg.text))
    process.DEBUG = True
    
    poly = Poly()
    poly.compile('-scratch-', '', 'fun p x y = x + y\n', test_handler)
    poly.compile('-scratch-', '', 'fun p x y = x + y\n', test_handler)
    
    time.sleep(2)
    
    poly.compile('-scratch-', '', 'fun p x y = x + y\n', test_handler)
    
    time.sleep(2)
    
    del(poly)
    
    

