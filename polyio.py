import sublime
import threading
import time


class Spinner(threading.Thread):
    def __init__(self, message):
        threading.Thread.__init__(self)
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


spinner_lock = threading.Lock()
active_spinners = []


def start_spinner(message):
    global active_spinners, spinner_lock
    spinner_lock.acquire()
    
    spinner = Spinner(message)
    spinner.start()
    active_spinners.append(spinner)
    
    spinner_lock.release()
    return spinner


def stop_spinner(spinner):
    global active_spinners, spinner_lock
    spinner_lock.acquire()
    
    spinner.stop()
    if spinner in active_spinners:
        active_spinners.remove(spinner)
    
    spinner_lock.release()


def stop_all_spinners():
    global active_spinners, spinner_lock
    spinner_lock.acquire()
    
    for spinner in active_spinners:
        spinner.stop()
    active_spinners = []
    
    spinner_lock.release()


_output_view = None

def output_view():
    global _output_view
    if _output_view == None:
        _output_view = sublime.active_window().get_output_panel("poly")
    return _output_view


def show_output_view():
    output_view() # make sure view has been created
    sublime.active_window().run_command("show_panel", {"panel": "output.poly"})


def output(text):
    ov = output_view()
    # selection_was_at_end = (len(ov.sel()) == 1
    #     and ov.sel()[0]
    #         == sublime.Region(ov.size()))
    ov.set_read_only(False)
    edit = ov.begin_edit()
    ov.insert(edit, ov.size(), text)
    # if selection_was_at_end:
    ov.show(ov.size())
    ov.end_edit(edit)
    ov.set_read_only(True)


def println(text=''):
    output(text + "\n")

