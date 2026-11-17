"""Build/output boundary tests; opaque class fixtures are not JVM validation."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import shutil
import subprocess
import sys
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/build_pixelmon_render.py'
spec = importlib.util.spec_from_file_location('render_build', SCRIPT)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
sys.path.insert(0, str(SCRIPT.parent))
import export_forge_client as client


class PixelmonRenderBuildTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_tracked_release_receipt_matches_sources_recipe_and_exporter(self):
        root = SCRIPT.parent.parent
        receipt = json.loads((root/'compat/pixelmon-render-build.json').read_text())
        sources = sorted(build.SOURCE.rglob('*.java')) + sorted(
            path for path in (build.SOURCE/'resources').rglob('*') if path.is_file())
        self.assertEqual(receipt['source_sha256'], {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources})
        self.assertEqual(receipt['recipe_path'], SCRIPT.relative_to(root).as_posix())
        self.assertEqual(receipt['recipe_sha256'], hashlib.sha256(SCRIPT.read_bytes()).hexdigest())
        self.assertEqual(receipt['sha256'], client.RENDER_PATCH_SHA256)
        self.assertEqual(receipt['input_sha256'], build.PINS)
        self.assertEqual({'mods/'+name: value for name, value in receipt['input_sha256'].items()},
                         client.RENDER_TARGET_PINS)
        self.assertEqual(receipt['minecraft_client_sha256'], build.CLIENT_SHA256)
        self.assertEqual(receipt['defaults'], {'vertices': True, 'advance': True})
        self.assertIn(receipt['version'], client.RENDER_PATCH_NAME)

    def require_java17(self):
        version=subprocess.check_output([shutil.which('javac'),'-version'],text=True).strip()
        if not version.startswith('javac 17.'):
            self.skipTest('Java 17 required, matching the build controller')

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

    @unittest.skipUnless(shutil.which('java') and shutil.which('javac'), 'JDK required')
    def test_java_launcher_handles_classpath_beyond_windows_command_line_limit(self):
        self.require_java17()
        source=self.root/'LongClasspath.java'
        source.write_text('public class LongClasspath { public static void main(String[] args) {'
            'if(System.getProperty("java.class.path").length()<40000) throw new AssertionError();'
            'if(!args[0].equals("space and \\\"quote\\\"")) throw new AssertionError(args[0]);'
            'System.out.println("LONG_CLASSPATH_PASS"); }}',encoding='utf-8')
        subprocess.run([shutil.which('javac'),str(source)],check=True)
        classpath=os.pathsep.join([str(self.root)]+[str(self.root/('unused_'+str(i)+'x'*80)) for i in range(500)])
        result=build.run_java(shutil.which('java'),['-cp',classpath,'LongClasspath','space and "quote"'],self.root,
                              capture_output=True,text=True)
        self.assertIn('LONG_CLASSPATH_PASS',result.stdout)

    @unittest.skipUnless(shutil.which('java') and shutil.which('javac'), 'JDK required')
    def test_argfiles_compile_and_launch_non_ascii_paths(self):
        self.require_java17()
        encoding=build.argfile_encoding()
        for name in ('한글 경로','café path'):
            try:
                name.encode(encoding,errors='strict')
                break
            except UnicodeEncodeError:
                continue
        else:
            self.skipTest('System argument encoding cannot represent a non-ASCII fixture')
        root=self.root/name
        root.mkdir()
        source=root/'UnicodePath.java'
        source.write_text('public class UnicodePath { public static void main(String[] args) {'
            'System.out.println("UNICODE_PATH_PASS"); }}',encoding='utf-8')
        classes=root/'classes'
        build.compile_java(shutil.which('javac'),[source],str(root),classes,root)
        result=build.run_java(shutil.which('java'),['-cp',str(classes),'UnicodePath'],root,
                              capture_output=True,text=True)
        self.assertIn('UNICODE_PATH_PASS',result.stdout)

    def test_unencodable_argument_is_rejected_before_writing_argfile(self):
        output=self.root/'invalid.args'
        with self.assertRaises(UnicodeEncodeError):
            build.write_argfile(output,['\ud800'])
        self.assertFalse(output.exists())

    def test_classpath_inventory_records_each_selected_binary_once(self):
        libraries=self.root/'libraries';libraries.mkdir()
        first=libraries/'first.jar';second=libraries/'second.jar';mod=self.root/'mod.jar'
        first.write_bytes(b'first');second.write_bytes(b'second');mod.write_bytes(b'mod')
        paths,receipt=build.classpath_inventory(libraries,[first,second,first],[mod])
        self.assertEqual(paths,[first,second,mod])
        self.assertEqual(receipt,[{'scope':'libraries','path':'first.jar','sha256':hashlib.sha256(b'first').hexdigest()},
            {'scope':'libraries','path':'second.jar','sha256':hashlib.sha256(b'second').hexdigest()},
            {'scope':'mods','path':'mod.jar','sha256':hashlib.sha256(b'mod').hexdigest()}])

    def test_pinned_lwjgl_precedes_older_cached_instance_libraries(self):
        libraries=self.root/'libraries'
        old=libraries/'org/lwjgl/lwjgl/3.2.2/lwjgl-3.2.2.jar'
        selected=libraries/'org/lwjgl/lwjgl/3.3.1/lwjgl-3.3.1.jar'
        for path in (old,selected):
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'library fixture')
        paths,_=build.classpath_inventory(libraries,[old,selected],[])
        self.assertEqual(paths,[selected,old])


if __name__ == '__main__':
    unittest.main()
