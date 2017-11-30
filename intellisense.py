# simple program to demonstrate intellisense for Oracle SQL statements

import sys
import itertools
import os

import cx_Oracle

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion

NUMBER_OF_SUGGESTIONS = 30

# what is context
# a.b.c
# return list of . dot separated values

def wordchar(c):
    return c.lower() in "abcdefghijklmnopqrstuvwxyz1234567890_$#"

# assumption char at pos is wordchar
# return position where not wordchar
def next_break(doc, pos):
    while pos>=0 and wordchar(doc[pos]):
        pos = pos - 1
    return pos

def context(text, pos):
    if pos == 0:
        return None
    # the first char is at pos-1
    if text[pos-1] == "." and pos>=2 and wordchar(text[pos-2]):
        pos2 = next_break(text, pos-2)
        return (text[pos2+1: pos-1],"")
    
    if not wordchar(text[pos-1]):
        return None
    pos2 = next_break(text, pos-1)
    if pos2 <=0 or text[pos2] != "." or not wordchar(text[pos2-1]):
        return (text[pos2+1:pos],)
    pos3 = next_break(text, pos2-1)
    return (text[pos3+1:pos2], text[pos2+1:pos])

def next_non_ws(text, pos):
    while pos < len(text) and text[pos].isspace():
        pos = pos + 1
    return pos

def next_word(text, pos):
    while True:
        if pos >=len(text):
            return None
        if wordchar(text[pos]):
            return pos
        pos = pos + 1

def word_end(text, pos):
    if pos >= len(text) or not wordchar(text[pos]):
        return pos
    else:
        return word_end(text, pos+1)

def find_alias_pairs(text):
    # find text whitespace word
    res = []
    pos = 0
    while True:
        pos2 = next_word(text,pos)
        if pos2 is None:
            return res
        # pos2 is start of word
        pos3 = word_end(text, pos2)
        # pos3 is position after word
        if pos3 >= len(text) or not text[pos3].isspace():
            pos = pos3
            continue
        pos4 = next_non_ws(text, pos3)
        if pos4 >= len(text):
            return res
        if wordchar(text[pos4]):
            pos5 = word_end(text, pos4)
            res.append((text[pos4:pos5],text[pos2:pos3]))
            pos = pos4
        else:
            pos = pos4
    

# data is # list of synonyms, list of tables
# synonym ist (synonym_name, table_name)
# a list of tables with a list of columns
# table is (table_name, list of columns (0string))

class DbData(object):

    def __init__(self):
        self.synonyms = [] # synonym, owner, table
        self.tables = []
        self.user = None

    def init(self, con):
        cur = con.cursor()
        cur.execute("select user from dual")
        for r in cur.fetchall():
            self.user = r[0]
        cur.close()
        cur = con.cursor()
        cur.execute("select owner, table_name, column_name from all_tab_columns order by 1,2,3")
        l = cur.fetchall()
        for tab, cols in itertools.groupby(l, lambda r: (r[0], r[1])):
            cols2 = list(map(lambda col: col[2], cols))
            self.tables.append((tab, cols2))
        cur.close()
        cur = con.cursor()
        cur.execute("""
    select synonym_name, table_owner, table_name 
      from all_synonyms 
     where owner in ('PUBLIC', user) 
      and (table_owner, table_name) 
        in (select owner, table_name from all_tables union all select owner, view_name from all_views )""")
        for r in cur.fetchall():
            self.synonyms.append((r[0], r[1], r[2]))
        cur.close()

    def suggest_table(self, tabstart):
        tabstart = tabstart.upper()
        res = []
        for (tab, _) in self.tables:
            if tab[1].startswith(tabstart):
                res.append(tab[1])
        for (sy, _,  _) in self.synonyms:
            if sy.startswith(tabstart) and sy not in res:
                res.append(sy)
        return sorted(res)

    def suggest_column_(self, owner, table, colstart):
        for ((owner_,tab_), cols) in self.tables:
            if owner == owner_ and table == tab_:
                res = []
                for c in cols:
                    if c.startswith(colstart):
                        res.append(c)
                return res
        return None

    def suggest_column(self, table, colstart):
        table = table.upper()
        colstart = colstart.upper()
        res = self.suggest_column_(self.user, table, colstart)
        if not res is None:
            return res
        for (synonym, owner_, tab_) in self.synonyms:
            if synonym == table:
                res = self.suggest_column_(owner_, tab_, colstart)
                if res is None:
                    return []
                else:
                    return res
        return []    

def find_tables_for_alias(text, alias):
    #print(find_alias_pairs(text.upper()))
    alias = alias.upper()
    yield alias
    for (a, tab) in find_alias_pairs(text.upper()):
        if alias == a:
            yield tab
            
class OracleCompleter(Completer):

    def __init__(self, dbdata):
        self.dbdata = dbdata

    def get_completions(self, document, complete_event):
        if not complete_event.completion_requested:
            return
        a = context(document.text, document.cursor_position)
        if a is None or len(a)==1:
            if a is None:
                a= ""
            else:
                a = a[0]
            i = 0
            for tab in self.dbdata.suggest_table(a):
                yield  Completion(tab, start_position=-len(a))
                i=i+1
                if i >= NUMBER_OF_SUGGESTIONS:
                    break
            return
        (tab,colstart) = a
        i=0
        for table in find_tables_for_alias(document.text, tab):
            for col in self.dbdata.suggest_column(table, colstart):
                yield Completion(col, start_position=-len(colstart))
                i=i+1
                if i >= NUMBER_OF_SUGGESTIONS:
                    break
        
        return

def print_table(rows):
    rows = list(rows)
    if len(rows) ==0:
        print("-- nix --")
        return
    ncols = len(rows[0])
    widths = [1] * ncols
    for row in rows:
        i = 0
        for c in row:
            w = len(str(c))
            if w > widths[i]:
                widths[i] = w
            i = i+1
    for row in rows:
        sys.stdout.write("|")
        i=0
        for c in row:
            sys.stdout.write(str(c).ljust(widths[i]) +"|")
            i = i+1
        sys.stdout.write("\n")
            

def connect(constr):
    if constr.upper().startswith("SYS/"):
        con = cx_Oracle.connect(constr, mode=cx_Oracle.SYSDBA)
    else:
        con = cx_Oracle.connect(constr)
    return con

def exec_query(con, sql):
    cur = con.cursor()
    try:
        cur.execute(sql)
        a = cur.fetchall()
        print_table(a)
    finally:
        cur.close()

    
def main():
    constr = sys.argv[1]
    con = connect(constr)
    dbdata = DbData()
    dbdata.init(con)
    ora_completer = OracleCompleter(dbdata)
    while True:
        text = prompt('> ', completer=ora_completer, multiline=True)
        if text == "":
            break
        try :
            exec_query(con, text)
        except Exception as e:
            print(e)


if __name__ == '__main__':
    main()
                
