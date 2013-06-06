import sublime
import sublime_plugin
import poly

class PolyConsoleHereCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()
        poly.console.ConsoleThread(
            view.file_name(),
            view.settings().get('poly_bin'),
            view.settings().get('terminal')
        ).start()

