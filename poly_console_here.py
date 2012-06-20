import sublime
import sublime_plugin
from poly import ConsoleThread

class PolyConsoleHereCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()
        ConsoleThread(
            view.file_name(),
            view.settings().get('poly_bin'),
            view.settings().get('terminal')
        ).start()

