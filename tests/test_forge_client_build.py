import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import export_forge_client as client


class ForgeClientBuildTest(unittest.TestCase):
    """Archive fixtures test packaging; they are never launched as game mods."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.server, self.extras = self.root/'server', self.root/'extras'
        (self.server/'mods').mkdir(parents=True)
        (self.server/'kubejs/server_scripts').mkdir(parents=True)
        self.extras.mkdir()
        (self.server/'.psa-forge-candidate.json').write_text('{}')
        self.files = []
        for name, kind, side, data in [('shared.jar','mod','both',b'shared fixture'),
                ('client.jar','mod','client',b'client fixture'), ('resource.zip','resourcepack','client',b'resource fixture'),
                ('shader.zip','shaderpack','client',b'shader fixture')]:
            path = client.target_path(kind, name)
            source = self.server/path if side=='both' else self.extras/name
            source.write_bytes(data)
            self.files.append({'path':path,'kind':kind,'side':side,'project_id':len(self.files)+1,
                'file_id':len(self.files)+11,'size':len(data),'hashes':self.hashes(data),'url':'https://example.test/'+name})
        self.pixel = self.server/'mods/Pixelmon-1.20.1-9.2.3-universal.jar'
        self.replacement = 'data/pixelmon/spawn_replacement/test.json'
        with zipfile.ZipFile(self.pixel,'w') as z:
            z.writestr(self.replacement,'{}')
        self.port = self.server/'mods/psa-aeronautics-experimental-forge-1.20.1.jar'
        self.port.write_bytes(b'port archive fixture')
        neutral = (json.dumps({'enabled':False,'detection_logic':'simple','replaced_mobs':[],
            'replacement_logic':'simple','specs':[]},indent=2)+'\n').encode()
        target=self.server/'kubejs'/self.replacement;target.parent.mkdir(parents=True);target.write_bytes(neutral)
        (self.server/'kubejs/server_scripts/init.js').write_bytes(b'// fixture')
        self.overrides={'kubejs/server_scripts/init.js':b'// fixture','shaderpacks/shader.zip':b'shader fixture'}
        self.society=self.root/'society.zip';self.output=self.root/'out/full.mrpack'
        self.lock={'minecraft':'1.20.1','forge':'47.4.20','society':'fixture','files':self.files}
        self.write_base()
        (self.root/'forge-candidate-lock.json').write_text('{}')
        for name,value in [('ROOT',self.root),('EXPECTED_FILES',4),('EXPECTED_SHARED',1),('EXPECTED_REPLACEMENTS',1),
                ('PIXELMON_SHA256',client.digest(self.pixel)),('PORT_SHA256',client.digest(self.port))]:
            context=patch.object(client,name,value);context.start();self.addCleanup(context.stop)

    @staticmethod
    def hashes(data):
        return {a:hashlib.new(a,data).hexdigest() for a in ['sha1','sha512']}

    def write_base(self):
        with zipfile.ZipFile(self.society,'w') as z:
            z.writestr('manifest.json',json.dumps({'files':[{'projectID':f['project_id'],'fileID':f['file_id']} for f in self.files]}))
            for name,data in self.overrides.items():z.writestr('overrides/'+name,data)
        self.lock['base_pack']={'size':self.society.stat().st_size,'sha1':client.digest(self.society,'sha1')}
        self.write_lock()

    def write_lock(self):
        (self.root/'forge-client-lock.json').write_text(json.dumps(self.lock))

    def build(self):
        return client.build(self.server,self.extras,self.society,self.output)

    def assert_no_export(self):
        with self.assertRaises(ValueError):self.build()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.parent.exists())

    def test_real_build_places_resources_and_deduplicates_identical_shader(self):
        report=self.build()
        self.assertEqual(report['mod_jars'],4)
        with zipfile.ZipFile(self.output) as z:
            self.assertEqual(z.read('overrides/mods/shared.jar'),b'shared fixture')
            self.assertEqual(z.read('overrides/resourcepacks/resource.zip'),b'resource fixture')
            self.assertEqual(z.read('overrides/shaderpacks/shader.zip'),b'shader fixture')
            self.assertNotIn('overrides/mods/resource.zip',z.namelist())
            self.assertEqual(z.namelist().count('overrides/shaderpacks/shader.zip'),1)

    def test_kubejs_mismatch_fails_before_output(self):
        (self.server/'kubejs/server_scripts/init.js').write_bytes(b'changed')
        self.assert_no_export()

    def test_extra_server_jar_fails_before_output(self):
        (self.server/'mods/extra.jar').write_bytes(b'extra')
        self.assert_no_export()

    def test_different_bundled_shader_fails_before_output(self):
        self.overrides['shaderpacks/shader.zip']=b'different';self.write_base()
        self.assert_no_export()

    def test_windows_collision_fails_before_output(self):
        self.overrides['resourcepacks/RESOURCE.zip']=b'other';self.write_base()
        self.assert_no_export()

    def test_existing_export_is_preserved(self):
        self.output.parent.mkdir();self.output.write_bytes(b'existing artifact')
        with self.assertRaises(ValueError):self.build()
        self.assertEqual(self.output.read_bytes(),b'existing artifact')

    def test_client_override_replaces_old_file_and_checks_java_target(self):
        replacement=self.extras/'camera-new.jar'
        with zipfile.ZipFile(replacement,'w') as z:
            z.writestr('camera/Target.class',bytes.fromhex('cafebabe0000003d'))
        entry={'replaces_path':'mods/client.jar','path':'mods/camera-new.jar','kind':'mod','side':'client',
            'size':replacement.stat().st_size,'hashes':self.hashes(replacement.read_bytes()),
            'url':'https://example.test/camera-new.jar','required_classes':['camera/Target.class'],'reason':'fixture compatibility'}
        self.lock['client_overrides']=[entry];self.write_lock();self.build()
        with zipfile.ZipFile(self.output) as z:
            self.assertIn('overrides/mods/camera-new.jar',z.namelist())
            self.assertNotIn('overrides/mods/client.jar',z.namelist())

    def test_shared_mod_cannot_be_replaced_by_client_override(self):
        self.lock['client_overrides']=[{'replaces_path':'mods/shared.jar'}];self.write_lock()
        self.assert_no_export()


if __name__=='__main__':unittest.main()
