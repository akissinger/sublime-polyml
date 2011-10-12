import sublime
import sublime_plugin
import os
import time
import poly
from threading import Thread

spinner = None

class Spinner(Thread):
    def __init__(self, message):
        Thread.__init__(self)
        self.message = message
        self.spin = True
    
    def stop(self):
        self.spin = False
    
    def run(self):
        spin_state = 0
        state_dir = 1
        size = 6
        while self.spin:
            sublime.set_timeout(lambda :
                sublime.status_message("{0}   [{1}={2}]".format(
                    self.message, ' ' * spin_state, ' ' * (size-spin_state)))
            , 0)
            
            if spin_state == 0: state_dir = 1
            elif spin_state == size: state_dir = -1
            
            spin_state += state_dir
            time.sleep(0.1)
        
        sublime.set_timeout(lambda : sublime.status_message(
            "{0}   [ done ]".format(self.message)), 0)
            
            
    

class RunPolyCommand(sublime_plugin.WindowCommand):
    def __init__(self, window):
        sublime_plugin.WindowCommand.__init__(self, window)
        self.poly = poly.Poly()
        self.current_job = None
    
    def output(self, text):
        selection_was_at_end = (len(self.output_view.sel()) == 1
            and self.output_view.sel()[0]
                == sublime.Region(self.output_view.size()))
        self.output_view.set_read_only(False)
        edit = self.output_view.begin_edit()
        self.output_view.insert(edit, self.output_view.size(), text)
        if selection_was_at_end:
            self.output_view.show(self.output_view.size())
        self.output_view.end_edit(edit)
        self.output_view.set_read_only(True)
        
    def println(self, text):
        self.output(text + "\n")
    
    
    def run(self):
        global spinner
        if self.current_job != None:
            print("Compile job already in progress...")
            return
        
        view = self.window.active_view()
        view.erase_regions('poly-errors')
        
        if not hasattr(self, 'output_view'):
            self.output_view = self.window.get_output_panel("poly")
        
        
        working_dir = os.path.dirname(self.window.active_view().file_name())
        file_name = os.path.basename(self.window.active_view().file_name())

        self.output_view.settings().set(
            "result_file_regex",
            "^(.*?):([0-9]*):.([0-9]*)-[0-9]*.:[ ](.*)$")
        
        self.output_view.settings().set("result_base_dir", working_dir)
        
        self.window.run_command("show_panel", {"panel": "output.poly"})
        self.println("Compiling code with Poly/ML...")
        
        preamble = "OS.FileSys.chDir \"" + working_dir + "\";\n"
        polysave = working_dir + "/.polysave/" + file_name + ".save"
        
        if os.path.exists(polysave):
            preamble += "PolyML.SaveState.loadState(\"" + polysave + "\");\n"
            preamble += "PolyML.fullGC ();\n"
        
        ml = view.substr(sublime.Region(0, len(view)))
        
        if (spinner != None): spinner.stop()
        spinner = Spinner("Compiling '{0}'".format(file_name))
        spinner.start()
        
        def handler(code, messages):
            global spinner
            spinner.stop()
            self.current_job = None
            
            def h():
                if code == 'S':
                    self.println("[Success]\n")
                else:
                    self.println("[{0}]\n".format(poly.translate_result_code(code)))
                    
                    error_regions = []
                    
                    for msg in messages:
                        line,start_col = view.rowcol(msg.start_pos)
                        line += 1  # counting lines from 1
                        end_col = view.rowcol(msg.end_pos)[1]
                        error_regions.append(sublime.Region(msg.start_pos, msg.end_pos))
                        
                        self.println("{0}:{1}:({2}-{3}): {4}".format(
                            os.path.basename(msg.filename),
                            line,
                            start_col + 1,
                            end_col + 1,
                            msg.text))
                    
                    view.add_regions('poly-errors', error_regions, 'constant', sublime.DRAW_OUTLINED)
            
            sublime.set_timeout(h,0) # execute h() on the main thread
            
        self.current_job = self.poly.compile(view.file_name(), preamble, ml, handler)



        