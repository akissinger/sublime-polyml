from sys import stdout
import time
import process
from process import PolyProcess, ProtocolError

poly_global = None

def global_instance(poly_bin='/usr/local/bin/poly'):
    global poly_global
    if poly_global == None:
        poly_global = Poly(poly_bin)
    return poly_global


class PolyMessage:
    def __init__(self, message_code, file_name, start_pos, end_pos, text):
        self.message_code = message_code
        self.file_name = file_name
        self.start_pos = int(start_pos)
        self.end_pos = int(end_pos)
        self.text = text
        
    def __str__(self):
        return "{0} '{1}' ({2}-{3}): {4}".format(
            'Error' if self.message_code == 'E' else 'Warning',
            self.file_name,
            self.start_pos,
            self.end_pos,
            self.text)
    
    def __repr__(self):
        return repr(self.__str__())


class PolyNode:
    def __init__(self, start=None, end=None, line=None, parse_tree=None,
                 file_name=None, properties=[]):
        self.start = start
        self.end = end
        self.line = line
        self.file_name = file_name
        self.parse_tree = parse_tree
        self.properties = properties
    def __repr__(self):
        return ("<PolyNode line=%s start=%s end=%s parse_tree=%s file_name=%s properties=%s>" %
            (self.start, self.line, self.end, self.parse_tree,
                self.file_name, repr(self.properties)))


class Poly:
    def __init__(self, poly_bin='/usr/local/bin/poly'):
        self.request_id = 0
        self.poly_bin = poly_bin
        self.process = None
        self.compile_in_progress = False
        self.parse_trees = {}
    
    def has_built(self, path):
        return (path in self.parse_trees.keys())
    
    def ensure_poly_running(self):
        if self.process == None or not self.process.is_alive():
            self.process = PolyProcess(self.poly_bin)
    
    def print_info_about_symbol(self, file, offset):
        self.ensure_poly_running()
        # rid = self.process.send_request(
        #         'O', [file, ])
    
    def node_for_position(self, path, position):
        if path in self.parse_trees.keys():
            node = PolyNode()
            node.file_name = path
            p = self.process.sync_request('O',
                [self.parse_trees[path], position, position])
            p.popcode('O')
            p.pop() # ignire RID
            p.popcode(',')
            node.parse_tree = p.popint()
            p.popcode(',')
            node.start = p.popint()
            p.popcode(',')
            node.end = p.popint()
            while p.popcode().code == ',':
                node.properties.append(p.popstr())
            return node
        else:
            return None
    
    def type_for_node(self, node):
        if 'T' in node.properties:
            p = self.process.sync_request('T',
                [node.parse_tree, node.start, node.end])
            p.popcode('T')
            for i in range(8): p.pop() # ignore info about the ident.
            return p.popstr()
        else:
            return None
    
    def declaration_for_node(self, node):
        if 'I' in node.properties:
            dnode = PolyNode()
            p = self.process.sync_request('I',
                [node.parse_tree, node.start, node.end])
            
            p.popcode('I')
            for i in range(8): p.pop() # ignore info about the ident.
            dnode.file_name = p.popstr()
            p.popcode(',')
            dnode.line = p.popint()
            p.popcode(',')
            dnode.start = p.popint()
            p.popcode(',')
            dnode.end = p.popint()
            
            if dnode.file_name in self.parse_trees.keys():
                dnode.parse_tree = self.parse_trees[dnode.file_name]
            
            return dnode
        else:
            return None
    
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
            self.parse_trees[file] = p.pop() # save parse tree ID
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
                file_name = p.popstr()
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
                
                messages.append(PolyMessage(message_code, file_name, start_pos, end_pos, text))
            
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
            print('{0}:({1}--{2}): {3}\n'.format(msg.file_name, msg.start_pos, msg.end_pos, msg.text))
    process.DEBUG = True
    
    poly = Poly()
    poly.compile('-scratch-', '', 'fun p x y = x + y\n', test_handler)
    poly.compile('-scratch-', '', 'fun p x y = x + y\n', test_handler)
    
    time.sleep(2)
    
    poly.compile('-scratch-', '', 'fun p x y = x + y\n', test_handler)
    
    time.sleep(2)
    
    del(poly)
    
    

