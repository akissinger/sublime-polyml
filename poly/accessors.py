import re

class Record:
	def __init__(self):
		self.fields = []
		self.maxw = 0
		self.type = None
		self.constructor = None
	def add_field(self,field):
		self.fields.append(field)
		if len(field.name) > self.maxw: self.maxw = len(field.name)

class Field:
	def __init__(self, name=None, typ=None):
		self.name = name
		self.type = typ
	def __repr__(self):
		return ("<Field name=%s type=%s>" % (self.name, self.type))

def parse_rec(rec_str):
	# kill comments, tabs, and line breaks
	rec_str = re.sub('\\(\\*.*?\\*\\)', '', rec_str.replace('\n','').replace('\t',' '))

	# grab record contents
	m = re.match('\\s*datatype\\s+(\\w*)\\s*=\\s*(\\w*)\\s*of\\s*\\{\\s*(.*)\\s*\\}\\s*', rec_str)

	if not m: return None

	rec = Record()
	rec.type = m.group(1).strip()
	rec.constructor = m.group(2).strip()

	field_strs = re.split('\\s*,\\s*', m.group(3))

	for s in field_strs:
		arr = re.split('\\s*:\\s*', s)
		if len(arr) != 2: return None

		arr[1] = arr[1].strip()
		if re.search('->|\\*', arr[1]):
			arr[1] = '(' + arr[1] + ')'

		rec.add_field(Field(arr[0],arr[1]))
	return rec

def sig_for_record(rec_str):
	rec = parse_rec(rec_str)
	if rec == None: return None
	out = ''


	for field in rec.fields:
		out += '  val update_{0} : ({1} -> {1}) -> {2} -> {2}\n'.format(field.name.ljust(rec.maxw), field.type, rec.type)

	for field in rec.fields:
		out += '  val get_{0}    : {2} -> {1}\n'.format(field.name.ljust(rec.maxw), field.type, rec.type)

	for field in rec.fields:
		out += '  val set_{0}    : {1} -> {2} -> {2}\n'.format(field.name.ljust(rec.maxw), field.type, rec.type)

	return out

def struct_for_record(rec_str):
	rec = parse_rec(rec_str)
	if rec == None: return None
	out = ''

	maxw = 0
	for field in rec.fields:
		if len(field.name) > maxw: maxw = len(field.name)

	for field in rec.fields:
		assigns = []
		for f2 in rec.fields:
			if field.name==f2.name: assigns.append('    {0} = f(#{1} r)'.format(f2.name.ljust(rec.maxw), f2.name))
			else: assigns.append('    {0} = #{1} r'.format(f2.name.ljust(rec.maxw), f2.name))
		out += '  fun update_{0} f ({1} r) = {1} {{\n{2}\n  }}\n\n'.format(field.name, rec.constructor, ',\n'.join(assigns))

	for field in rec.fields:
		out += '  fun get_{0} ({2} r) = #{1} r\n'.format(field.name.ljust(rec.maxw), field.name, rec.constructor)

	out += '\n'

	for field in rec.fields:
		out += '  val set_{0}    = update_{0} o K\n'.format(field.name.ljust(rec.maxw))

	return out

def run_tests():
	# a typical record
	record = """
	  datatype T = MatchState of {
	    (* names context for fresh names when copying bboxes in pat *)
	    names        : V.NSet.T * E.NSet.T,
	    (* pattern and target graphs *)
	    pat          : G.T,
	    tgt          : G.T,
	    (* internal vertex mapping from pat to tgt *)
	    vmap         : VInjEndo.T,
	    (* circles, node-vertices, and wire-vertices to be matched *)
	    u_circles    : V.NSet.T,
	    u_nodeverts  : V.NSet.T,
	    u_wireverts  : V.NSet.T,
	    u_bare_wires : V.NSet.T,
	    (* partially matched node-vertices *)
	    p_nodeverts  : V.NSet.T,
	    (* partially matched node-vertices, scheduled for re-matching *)
	    ps_nodeverts : V.NSet.T
	  }
	"""
	
	print(sig_for_record(record))
	print(struct_for_record(record))

if __name__ == '__main__':
    run_tests()

