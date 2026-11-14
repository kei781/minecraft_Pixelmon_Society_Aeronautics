import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import forge_key_defaults as keys
from stage_forge_candidate import PIXELMON_SHA256, PORT_SHA256

TABLE = ROOT / 'compat/client-keys/default-keys.json'


class DefaultKeyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.table = json.loads(TABLE.read_text())
        self.moves = len(self.table['moved'])
        # Society's side of each shared key, and one binding that keeps a modifier.
        self.lines = ['lang:en_us', 'key_key.jump:key.keyboard.space:NONE',
                      'key_key.jei.toggleOverlay:key.keyboard.o:CONTROL']
        for move in self.table['moved']:
            self.lines += ['key_%s:%s:NONE' % (other, move['from']) for other in move['acts_together_with']]
        self.lines.append('soundCategory_master:1.0')

    def apply(self, table=None, lines=None, expected=None):
        path = Path(self.temp.name) / 'default-keys.json'
        path.write_text(json.dumps(self.table if table is None else table))
        overrides = {keys.OPTIONS: ('\n'.join(self.lines if lines is None else lines) + '\n').encode()}
        receipt = keys.apply(overrides, path, PIXELMON_SHA256, PORT_SHA256, self.moves if expected is None else expected)
        return overrides[keys.OPTIONS].decode().splitlines(), receipt

    def changed(self, edit):
        table = copy.deepcopy(self.table)
        edit(table)
        return table

    def test_shipped_table_gives_each_moved_binding_one_free_key_after_the_last_key_line(self):
        lines, receipt = self.apply()
        added = ['key_%s:%s:NONE' % (move['binding'], move['to']) for move in self.table['moved']]
        self.assertEqual(self.moves, 6)
        self.assertEqual(receipt['added'], added)
        self.assertEqual(lines[:-1], self.lines[:-1] + added)
        self.assertEqual(lines[-1], 'soundCategory_master:1.0')
        shipped = keys.bindings(lines)
        used = [key for key, _ in shipped.values()]
        for move in self.table['moved']:
            self.assertEqual(used.count(move['to']), 1)
            self.assertEqual(shipped[move['binding']], (move['to'], 'NONE'))

    def test_shipped_table_is_pinned_to_the_shipped_pixelmon_and_port_jars(self):
        self.assertEqual(self.table['pixelmon_sha256'], PIXELMON_SHA256)
        self.assertEqual(self.table['port_sha256'], PORT_SHA256)
        path = Path(self.temp.name) / 'default-keys.json'
        path.write_text(json.dumps(self.table))
        for pixelmon, port in [('0' * 64, PORT_SHA256), (PIXELMON_SHA256, '0' * 64)]:
            with self.assertRaisesRegex(ValueError, 'different Pixelmon or port'):
                keys.apply({keys.OPTIONS: b'lang:en_us\n'}, path, pixelmon, port, self.moves)

    def test_every_key_name_the_game_reads_is_known_and_the_unbound_key_is_not_a_target(self):
        self.assertEqual(len(keys.KEYBOARD_KEYS), 120)
        self.assertNotIn('key.keyboard.unknown', keys.KEYBOARD_KEYS)
        for name in ['key.keyboard.semi', 'key.keyboard.unknown', 'key.mouse.4', 'semicolon']:
            table = self.changed(lambda table: table['moved'][0].update(to=name))
            with self.assertRaisesRegex(ValueError, 'Free keyboard key required'):
                self.apply(table)

    def test_target_key_used_by_any_other_default_is_refused(self):
        cases = {'a key line of the file': 'key.keyboard.space',
                 'a key line that needs a modifier': 'key.keyboard.o',
                 'a coded Pixelmon default': 'key.keyboard.i',
                 'another moved binding': self.table['moved'][1]['to']}
        for reason, name in cases.items():
            with self.subTest(reason):
                table = self.changed(lambda table: table['moved'][0].update(to=name))
                with self.assertRaisesRegex(ValueError, 'Free keyboard key required'):
                    self.apply(table)

    def test_move_is_refused_when_the_shared_society_binding_is_no_longer_on_that_plain_key(self):
        other = self.table['moved'][0]['acts_together_with'][0]
        old = self.table['moved'][0]['from']
        for replacement in ['key_%s:key.keyboard.f9:NONE' % other, 'key_%s:%s:CONTROL' % (other, old), None]:
            lines = [line for line in self.lines if not line.startswith('key_%s:' % other)]
            if replacement:
                lines.insert(1, replacement)
            with self.assertRaisesRegex(ValueError, 'Shared default key differs'):
                self.apply(lines=lines)
        table = self.changed(lambda table: table['moved'][0].update(acts_together_with=[]))
        with self.assertRaisesRegex(ValueError, 'Shared default key differs'):
            self.apply(table)

    def test_table_that_disagrees_with_the_coded_default_or_the_expected_count_is_refused(self):
        table = self.changed(lambda table: table['moved'][0].update({'from': 'key.keyboard.j'}))
        with self.assertRaisesRegex(ValueError, 'Coded default differs'):
            self.apply(table)
        table = self.changed(lambda table: table['moved'].pop())
        with self.assertRaisesRegex(ValueError, 'Unexpected default key table'):
            self.apply(table)
        table = self.changed(lambda table: table['moved'].__setitem__(1, table['moved'][0]))
        with self.assertRaisesRegex(ValueError, 'Unexpected default key table'):
            self.apply(table)

    def test_file_that_already_sets_a_pixelmon_key_or_repeats_a_binding_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'already sets a Pixelmon or port key'):
            self.apply(lines=self.lines + ['key_key.wiki:key.keyboard.k:NONE'])
        with self.assertRaisesRegex(ValueError, 'Unreadable default key line'):
            self.apply(lines=self.lines + ['key_key.jump:key.keyboard.j:NONE'])

    def test_file_is_left_alone_when_nothing_is_moved(self):
        table = self.changed(lambda table: table.update(moved=[]))
        lines, receipt = self.apply(table, expected=0)
        self.assertEqual(lines, self.lines)
        self.assertEqual(receipt['added'], [])


if __name__ == '__main__':
    unittest.main()
