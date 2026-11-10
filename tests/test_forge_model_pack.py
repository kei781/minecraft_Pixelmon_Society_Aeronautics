import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import forge_model_pack as model_pack


class ForgeModelPackTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.jar = Path(self.temp.name) / 'port.jar'
        self.name = 'assets/simulated/models/block/wheel.json'
        self.document = {'loader':'neoforge:obj','model':'simulated:models/block/wheel.obj',
            'flip_v':True,'textures':{'wheel':'simulated:block/wheel'},'display':{'gui':{'rotation':[30,40,50]}},
            'metadata':'neoforge:obj must remain here'}
        self.write_jar()

    def write_jar(self, include_obj=True):
        with zipfile.ZipFile(self.jar,'w') as z:
            z.writestr(self.name,json.dumps(self.document))
            z.writestr('assets/simulated/models/block/vanilla.json','{"parent":"minecraft:block/cube_all"}')
            z.writestr('example.class',b'fixture only, never loaded')
            if include_obj:z.writestr('assets/simulated/models/block/wheel.obj','mtllib wheel.mtl\n')
        self.sha = hashlib.sha256(self.jar.read_bytes()).hexdigest()

    def build(self):
        return model_pack.build(self.jar,self.sha,expected_models=1)

    def test_only_top_level_loader_changes_and_output_is_deterministic(self):
        data, receipt = self.build()
        self.assertEqual(data,self.build()[0])
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(set(z.namelist()),{self.name,'pack.mcmeta'})
            expected=dict(self.document,loader='forge:obj')
            self.assertEqual(json.loads(z.read(self.name)),expected)
            self.assertEqual(json.loads(z.read('pack.mcmeta'))['pack']['pack_format'],15)
        self.assertEqual(receipt['models'][0]['path'],self.name)

    def test_hash_mismatch_and_unknown_loader_are_rejected(self):
        with self.assertRaisesRegex(ValueError,'identity'):model_pack.build(self.jar,'0'*64,1)
        self.document['loader']='neoforge:unknown';self.write_jar()
        with self.assertRaisesRegex(ValueError,'Unsupported'):self.build()

    def test_missing_obj_and_changed_inventory_are_rejected(self):
        self.write_jar(include_obj=False)
        with self.assertRaisesRegex(ValueError,'Missing'):self.build()
        self.write_jar()
        with self.assertRaisesRegex(ValueError,'inventory'):model_pack.build(self.jar,self.sha,2)

    def test_enabling_preserves_existing_defaults_and_marks_compat_pack_required(self):
        config={'schema_version':2,'default_packs':['vanilla','file/old.zip'],'pack_overrides':{'file/old.zip':{'hidden':True}}}
        overrides={'config/resourcepackoverrides.json':json.dumps(config).encode(),
            'configureddefaults/options.txt':b'lang:ko_kr\nresourcePacks:["vanilla","file/old.zip"]\nfov:0.5\n'}
        model_pack.enable(overrides,b'fixture archive')
        new=json.loads(overrides['config/resourcepackoverrides.json'])
        self.assertEqual(new['default_packs'],config['default_packs']+[model_pack.PACK_ID])
        self.assertEqual(new['pack_overrides']['file/old.zip'],{'hidden':True})
        self.assertEqual(new['pack_overrides'][model_pack.PACK_ID],{'hidden':False,'required':True})
        self.assertIn(b'lang:ko_kr\n',overrides['configureddefaults/options.txt'])
        self.assertIn(b'\nfov:0.5\n',overrides['configureddefaults/options.txt'])

    def test_invalid_selections_do_not_mutate_input(self):
        for options in [b'lang:en_us\n',b'resourcePacks:{}\n',b'resourcePacks:[]\nresourcePacks:[]\n']:
            original={'config/resourcepackoverrides.json':b'{"schema_version":2,"default_packs":[],"pack_overrides":{}}',
                'configureddefaults/options.txt':options}
            overrides=dict(original)
            with self.assertRaises(ValueError):model_pack.enable(overrides,b'fixture archive')
            self.assertEqual(overrides,original)


if __name__=='__main__':unittest.main()
