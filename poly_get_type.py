import sublime
import sublime_plugin
import os
import poly
import polyio

class DescribePolySymbolCommand(sublime_plugin.WindowCommand):
    def __init__(self, window):
        sublime_plugin.WindowCommand.__init__(self, window)
        poly_bin = window.active_view().settings().get('poly_bin')
        if poly_bin == None: poly_bin = '/usr/local/bin/poly'
        self.poly = poly.global_instance(poly_bin)
    
    def run(self):
        view = self.window.active_view()
        polyio.show_output_view()
        path = self.window.active_view().file_name()
        
        if self.poly.has_built(path):
            position = view.sel()[0].begin()
            try:
                node = self.poly.node_for_position(path, position)
                name = view.substr(sublime.Region(node.start, node.end))
                ml_type = self.poly.type_for_node(node)
                
                if ml_type != None:
                    polyio.println('val %s : %s' % (name, ml_type))
                else:
                    polyio.println("Can't decribe %s" % name)
            except poly.process.Timeout:
                pass
            
            polyio.println()
        else:
            polyio.println('Recompile this file to get info about its symbols.')
            
        
