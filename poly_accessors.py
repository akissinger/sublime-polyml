import sublime
import sublime_plugin
import poly
import polyio

class PolyAccessorSigCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		text = self.view.substr(self.view.sel()[0])
		sublime.set_clipboard(poly.accessors.sig_for_record(text))
		
class PolyAccessorStructCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		text = self.view.substr(self.view.sel()[0])
		sublime.set_clipboard(poly.accessors.struct_for_record(text))