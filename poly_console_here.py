import sublime
import sublime_plugin
import os
import subprocess
import threading
import tempfile
import string

class ConsoleThread(threading.Thread):
    def __init__(self,path,term):
        threading.Thread.__init__(self)
        self.working_dir = os.path.dirname(path)
        self.file_name = os.path.basename(path)
        
        if term == None:
            self.term = 'xterm'
        else:
            self.term = term
        
    def run(self):
        (_,temp) = tempfile.mkstemp('.ML', 'poly_')
        f = open(temp, 'w')
        f.write("exception okay;\n")
        f.write("val result = PolyML.exception_trace (fn () => (\n")
        f.write("  OS.FileSys.chDir \"%s\";\n" % self.working_dir)
        
        polysave = self.working_dir + "/.polysave/" + self.file_name + ".save"
        if os.path.exists(polysave):
            f.write("  print \"Loading .polysave/%s.save...\\n\";\n" % self.file_name)
            f.write("  PolyML.SaveState.loadState(\"%s\");\n" % polysave)
            f.write("  PolyML.fullGC ();\n")
        
        f.write("  PolyML.Compiler.printDepth := 50;\n")
        f.write("  print \"Using %s...\\n\";\n" % self.file_name)
        f.write("  PolyML.use \"%s\"\n;" % self.file_name)
        f.write("okay)) handle e => e;\n")
        f.close()
        
        cmd = [self.term]
        poly_cmd = ["rlwrap", "-z", sublime.packages_path() + "/PolyML/poly_filter.pl",
            "poly", "--use", temp]
        
        if self.term == 'gnome-terminal':
            poly_cmd = [string.join(poly_cmd, ' ')]
            cmd += ['--disable-factory']
        elif self.term == 'konsole':
            cmd += ["--nofork"]
        
        cmd += ['-e'] + poly_cmd
        
        #print string.join(cmd, ' ')
        st = subprocess.call(cmd)
        #st = subprocess.call(['konsole','--nofork','--hold'])
        #print ("done: %d" % st)
        os.remove(temp)

class PolyConsoleHereCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()
        ConsoleThread(view.file_name(), view.settings().get('terminal')).start()

