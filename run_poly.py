import sublime
import sublime_plugin
import os
import time
import poly
import polyio
from threading import Thread
          

class RunPolyCommand(sublime_plugin.WindowCommand):
    def __init__(self, window):
        sublime_plugin.WindowCommand.__init__(self, window)
        self.poly = None
        self.current_job = None
    
    def run(self):
        view = self.window.active_view()
        
        poly_bin = view.settings().get('poly_bin')
        if poly_bin == None: poly_bin = '/usr/local/bin/poly'
        
        if self.poly == None or self.poly.poly_bin != poly_bin:
            self.poly = poly.global_instance(poly_bin)
        
        if self.current_job != None:
            print("Compile job already in progress...")
            return
        
        view.erase_regions('poly-errors')
        
        output_view = polyio.output_view()
        polyio.show_output_view()
        polyio.println("Compiling code with Poly/ML...")
        
        preamble = ""
        path = self.window.active_view().file_name()
        if path != None:
            working_dir = os.path.dirname(path)
            file_name = os.path.basename(path)
            output_view.settings().set("result_base_dir", working_dir)
            
            preamble = "OS.FileSys.chDir \"" + working_dir + "\";\n"
            polysave = working_dir + "/.polysave/" + file_name + ".save"
            
            if os.path.exists(polysave):
                preamble += "PolyML.SaveState.loadState(\"" + polysave + "\");\n"
                preamble += "PolyML.fullGC ();\n"
        else:
            path = "--scratch--"
            file_name = "--scratch--"

        output_view.settings().set(
            "result_file_regex",
            "^(.*?):([0-9]*):.([0-9]*)-[0-9]*.:[ ](.*)$")
        
        
        ml = view.substr(sublime.Region(0, len(view)))
        
        spinner = None
        
        def handler(code, messages):
            if spinner != None:
                polyio.stop_spinner(spinner)
            
            self.current_job = None
            
            def h():
                if code == 'S':
                    polyio.println("[Success]")
                else:
                    polyio.println("[{0}]\n".format(poly.translate_result_code(code)))
                    
                    error_regions = []
                    
                    for msg in messages:
                        line,start_col = view.rowcol(msg.location.start)
                        line += 1  # counting lines from 1
                        end_col = view.rowcol(msg.location.end)[1]
                        error_regions.append(sublime.Region(msg.location.start,
                                                            msg.location.end))
                        
                        polyio.println("{0}:{1}:({2}-{3}): {4}".format(
                            os.path.basename(msg.location.file_name),
                            line,
                            start_col + 1,
                            end_col + 1,
                            msg.text))
                    
                    view.add_regions('poly-errors', error_regions, 'constant', sublime.DRAW_OUTLINED)
            
            sublime.set_timeout(h,0) # execute h() on the main thread
        
        try:
            self.current_job = self.poly.compile(path, preamble, ml, handler)
        except poly.process.ProtocolError as e:
            polyio.println("Protocol Error: " + str(e))
            polyio.println("Check that 'poly_bin' is defined correctly in your user settings.")
        else:
            spinner = polyio.start_spinner("Compiling '{0}'".format(file_name))



        
