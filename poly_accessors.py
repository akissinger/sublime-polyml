import sublime
import sublime_plugin
import PolyML.poly
from . import polyio

class PolyAccessorSigCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		text = self.view.substr(self.view.sel()[0])
		sublime.set_clipboard(PolyML.poly.accessors.sig_for_record(text))
		
class PolyAccessorStructCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		text = self.view.substr(self.view.sel()[0])
		sublime.set_clipboard(PolyML.poly.accessors.struct_for_record(text))