import os
import subprocess
import sys
import threading
import tempfile
import string
import time

class ConsoleThread(threading.Thread):
    def __init__(self,path,poly_bin,term):
        threading.Thread.__init__(self)
        self.term = term
        if not self.term:
            if sys.platform.startswith('darwin'):
                term = 'Terminal.app'
            elif os.name == 'posix':
                term = 'xterm'
            else:
                raise ValueError("Cannot guess terminal on this platform")

        self.working_dir = os.path.dirname(path)
        self.file_name = os.path.basename(path)

        if poly_bin == None:
            self.poly_bin = 'poly'
        else:
            self.poly_bin = poly_bin

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

        filedir = os.path.dirname(os.path.abspath(__file__))
        poly_cmd = ["rlwrap", "-z", os.path.join(filedir, "poly_filter.pl"),
            self.poly_bin, "--use", temp]

        terminal_will_detach = True
        if self.term == 'gnome-terminal':
            cmd = [self.term, '--disable-factory', '-e'] + [string.join(poly_cmd, ' ')]
            terminal_will_detach = False
        elif self.term == 'konsole':
            cmd = [self.term, '--nofork', '-e'] + poly_cmd
            terminal_will_detach = False
        elif self.term == 'Terminal.app':
            # rlwrap needs pathname with a space in it to quoted twice
            poly_cmd[2] = "'\\\"%s\\\"'" % poly_cmd[2]
            cmd = ['osascript', '-e', 'tell application "Terminal"',
                '-e', "activate",
                '-e', "do script \"%s\"" % string.join(poly_cmd, ' '),
                '-e', "end tell"]
        elif self.term == 'xterm':
            cmd = [self.term, '-e'] + poly_cmd
            terminal_will_detach = False
        else:
            cmd = [self.term, '-e'] + poly_cmd

        print(cmd)
        st = subprocess.call(cmd)
        if terminal_will_detach:
            time.sleep(10) # give poly time to load tempfile before it is removed
        os.remove(temp)

