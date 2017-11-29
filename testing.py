import unittest

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion

from intellisense import *

class MyCustomCompleter(Completer):
    def get_completions(self, document, complete_event):
        if not complete_event.completion_requested:
            return
        print(document.cursor_position)
        yield Completion('completion', start_position=0)
        yield Completion('roland', start_position=0)

class TestIntellisense(unittest.TestCase):

    def xtest_1(self):
        text = prompt('> ', completer=MyCustomCompleter())

    def test_2(self):
        t = "abc. axyz.hkk "
        for i in range(len(t)):
            print(i,t[0:i],"->", context(t, i))

    def test_3(self):
        t = "hgf abb 2323 weer.ererer sdsd / sdsdsd hhjhj *s ,x suoi"
        print(find_alias_pairs(t))

if __name__ == '__main__':
    unittest.main()
