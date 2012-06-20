import re

"""Generate code from record datatypes.

This module speeds up creation of structures based around a record datatype by
generating the accessor signatures and implementations for you.

The implementation uses regular expressions to parse the record declaration, so
may not work on all records.
"""

class Record:
    """A (parsed) record datatype.

    fields -- a list of Field objects
    maxw -- the width of the longest field name
    type -- the ML type name assigned to the record
    constructor -- the type constructor for the record
    """

    def __init__(self):
        self.fields = []
        self.maxw = 0
        self.type = None
        self.constructor = None

    def add_field(self,field):
        """Adds a field to the record.

        field -- a Field object
        """
        self.fields.append(field)
        if len(field.name) > self.maxw: self.maxw = len(field.name)

class Field:
    """A field in a record datatype.

    name -- the name of the field (string)
    type -- the ML type of the field (string)
    """

    def __init__(self, name=None, typ=None):
        self.name = name
        self.type = typ

    def __repr__(self):
        return ("<Field name=%s type=%s>" % (self.name, self.type))

def parse_rec(rec_str):
    """Parses a record datatype declaration.

    rec_str -- the StandardML datatype record declaration

    A record declaration looks like
      datatype <type> = <constructor> of {
        field1_name : field1_type,
        field2_name : field2_type,
        [...]
        fieldN_name : fieldN_type
      }
    Comments and whitespace are ignored.  The only required whitespace is
    between "datatype" and the type name, and between the constructor name and
    "of".

    Returns a Record object if parsing was successful, or None.
    """
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
    """Generates accessor signatures for a record.

    rec_str -- the StandardML datatype record declaration (see parse_rec())

    For each field "fldnm" with type "fldtyp", it will generate an updater,
    getter and setter in the following form:
        val update_fldnm : (fldtyp -> fldtyp) -> rectyp -> rectyp
        val get_fldnm : rectyp -> fldtyp
        val set_fldnm : rectyp -> fldtyp -> fldtyp
    where rectyp is the type name of the record.

    Returns the StandardML code in a string, or None if parsing of rec_str
    failed.
    """
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
    """Generates accessor signatures for a record.

    rec_str -- the StandardML datatype record declaration (see parse_rec())

    See sig_for_record() for the generated function types.

    Note that the generated code makes use of the K function:
        fun K x _ = x
    which is not part of the standard basis.

    Returns the StandardML code in a string, or None if parsing of rec_str
    failed.
    """
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

