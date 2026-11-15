"""Build/output boundary tests; opaque class fixtures are not JVM validation."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/build_pixelmon_render.py'
spec = importlib.util.spec_from_file_location('render_build', SCRIPT)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class PixelmonRenderBuildTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_changed_or_missing_input_is_rejected(self):
        source = self.root / 'mods'
        source.mkdir()
        (source / 'fixture.jar').write_bytes(b'abc')
        pins = {'fixture.jar': hashlib.sha256(b'abc').hexdigest()}
        self.assertEqual(build.verify_inputs(source, pins), [source / 'fixture.jar'])
        (source / 'fixture.jar').write_bytes(b'abd')
        with self.assertRaisesRegex(ValueError, 'Pinned input differs'):
            build.verify_inputs(source, pins)
        with self.assertRaisesRegex(ValueError, 'Pinned input differs'):
            build.verify_inputs(source, {'missing.jar': pins['fixture.jar']})

    def test_output_guards_preserve_existing_files_and_installed_mods(self):
        existing = self.root / 'keep.jar'
        existing.write_bytes(b'keep')
        for path in (existing, self.root/'mods'/'candidate.jar', self.root/'MODS'/'candidate.jar',
                     self.root/'candidate.zip'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                build.fresh_output(path)
        self.assertEqual(existing.read_bytes(), b'keep')
        build.fresh_output(self.root/'candidate.jar')

    def test_packaging_is_deterministic_and_never_includes_upstream_classes(self):
        classes, resources = self.root/'classes', self.root/'resources'
        owned = classes/'dev/psa/pixelmonrender/Owned.class'
        owned.parent.mkdir(parents=True)
        owned.write_bytes(b'opaque fixture')
        resources.mkdir()
        (resources/'owned.json').write_text('{}')
        first, second = self.root/'first.jar', self.root/'second.jar'
        build.package_jar(classes, resources, first)
        build.package_jar(classes, resources, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        with zipfile.ZipFile(first) as jar:
            self.assertEqual(set(jar.namelist()), {'META-INF/MANIFEST.MF',
                'dev/psa/pixelmonrender/Owned.class', 'owned.json'})
        foreign = classes/'com/pixelmon/Foreign.class'
        foreign.parent.mkdir(parents=True)
        foreign.write_bytes(b'not owned')
        rejected = self.root/'rejected.jar'
        with self.assertRaisesRegex(ValueError, 'Non-authored'):
            build.package_jar(classes, resources, rejected)
        self.assertFalse(rejected.exists())


if __name__ == '__main__':
    unittest.main()
