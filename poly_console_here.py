import sublime
import sublime_plugin
import PolyML.poly

class PolyConsoleHereCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()
        PolyML.poly.console.ConsoleThread(
            view.file_name(),
            view.settings().get('poly_bin'),
            view.settings().get('terminal')
        ).start()

