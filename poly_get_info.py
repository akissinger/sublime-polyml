import sublime
import sublime_plugin
import os
import poly
import polyio

class DescribePolySymbolCommand(sublime_plugin.WindowCommand):
    def run(self):
        poly_bin = window.active_view().settings().get('poly_bin')
        if poly_bin == None: poly_bin = '/usr/local/bin/poly'
        poly_inst = poly.global_instance(poly_bin)

        view = self.window.active_view()
        polyio.show_output_view()
        path = self.window.active_view().file_name()
        
        if poly_inst.has_built(path):
            position = view.sel()[0].begin()
            try:
                node = poly_inst.node_for_position(path, position)
                name = view.substr(sublime.Region(node.start, node.end))
                ml_type = poly_inst.type_for_node(node)
                
                if ml_type != None:
                    polyio.println('val %s : %s' % (name, ml_type))
                else:
                    polyio.println("Can't decribe %s" % name)
            except poly.process.Timeout:
                pass
            
            polyio.println()
        else:
            polyio.println('Recompile this file to get info about its symbols.')
            
        
