import hashlib
import io
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
        self.fixture_data = {}
        for name, kind, side, data in [('shared.jar','mod','both',b'shared fixture'),
                ('client.jar','mod','client',b'client fixture'), ('resource.zip','resourcepack','client',b'resource fixture'),
                ('shader.zip','shaderpack','client',b'shader fixture')]:
            path = client.target_path(kind, name)
            data = self.archive_bytes({'fixture.txt': data})
            self.fixture_data[name] = data
            source = self.server/path if side=='both' else self.extras/name
            source.write_bytes(data)
            self.files.append({'path':path,'kind':kind,'side':side,'project_id':len(self.files)+1,
                'file_id':len(self.files)+11,'size':len(data),'hashes':self.hashes(data),'url':'https://example.test/'+name})
        alias = client.forge_item_model_alias
        model, texture = b'{"parent":"minecraft:item/generated"}', b'owned fixture texture'
        data = self.archive_bytes({alias.MODEL: model, alias.TEXTURE: texture})
        (self.server/alias.JAR).write_bytes(data)
        self.files.append({'path':alias.JAR,'kind':'mod','side':'both','project_id':5,'file_id':15,
            'size':len(data),'hashes':self.hashes(data),'url':'https://example.test/decorative.jar'})
        guard = patch.multiple(alias, JAR_SHA256=hashlib.sha256(data).hexdigest(),
            MODEL_SHA256=hashlib.sha256(model).hexdigest(), TEXTURE_SHA256=hashlib.sha256(texture).hexdigest())
        guard.start(); self.addCleanup(guard.stop)
        self.pixel = self.server/'mods/Pixelmon-1.20.1-9.2.3-universal.jar'
        self.replacement = 'data/pixelmon/spawn_replacement/test.json'
        with zipfile.ZipFile(self.pixel,'w') as z:
            z.writestr(self.replacement,'{}')
        self.port = self.server/'mods/psa-aeronautics-experimental-forge-1.20.1.jar'
        with zipfile.ZipFile(self.port, 'w') as z:
            z.writestr('assets/aeronautics/models/block/fixture.json', json.dumps({
                'loader':'neoforge:obj','model':'aeronautics:models/block/fixture.obj','flip_v':True}))
            z.writestr('assets/aeronautics/models/block/fixture.obj', 'mtllib fixture.mtl\n')
            z.writestr('assets/aeronautics/models/block/fixture.mtl', 'newmtl fixture\n')
        neutral = (json.dumps({'enabled':False,'detection_logic':'simple','replaced_mobs':[],
            'replacement_logic':'simple','specs':[]},indent=2)+'\n').encode()
        target=self.server/'kubejs'/self.replacement;target.parent.mkdir(parents=True);target.write_bytes(neutral)
        (self.server/'kubejs/server_scripts/init.js').write_bytes(b'// fixture')
        self.overrides={'kubejs/server_scripts/init.js':b'// fixture','shaderpacks/shader.zip':self.fixture_data['shader.zip'],
            'config/resourcepackoverrides.json':json.dumps({'schema_version':2,'default_packs':['vanilla'],
                'pack_overrides':{}}).encode(),
            'configureddefaults/options.txt':b'lang:en_us\nresourcePacks:["vanilla"]\n'
                b'key_key.curios.open.desc:key.keyboard.g:NONE\nsoundCategory_master:1.0\n'}
        self.loot_original = b'{"forge:conditions":[{"type":"forge:false"}]}'
        context = patch.object(client.forge_datapack_compat, 'RESOURCE_SHA256', hashlib.sha256(self.loot_original).hexdigest())
        context.start(); self.addCleanup(context.stop)
        self.overrides[client.forge_datapack_compat.RESOURCE] = self.loot_original
        loot_target = self.server/client.forge_datapack_compat.RESOURCE
        loot_target.parent.mkdir(parents=True)
        loot_target.write_bytes(client.forge_datapack_compat.normalize_resource(self.loot_original)[0])
        self.society=self.root/'society.zip';self.output=self.root/'out/full.mrpack'
        self.lock={'minecraft':'1.20.1','forge':'47.4.20','society':'fixture','files':self.files}
        self.write_base()
        (self.root/'forge-candidate-lock.json').write_text('{}')
        # This minimal archive fixture isolates the original alias/export invariants.
        # The full five-item batch is covered by dedicated controls and the real full-pack export.
        (self.root/'compat').mkdir()
        (self.root/'compat/item-model-aliases.json').write_text('[]')
        self.key_table={'pixelmon_sha256':client.digest(self.pixel),'port_sha256':client.digest(self.port),
            'coded_defaults':{'key.pokemonexternal':'key.keyboard.g'},
            'moved':[{'binding':'key.pokemonexternal','from':'key.keyboard.g','to':'key.keyboard.semicolon',
                'acts_together_with':['key.curios.open.desc'],'shares_new_key_with':[]}]}
        (self.root/'compat/client-keys').mkdir()
        self.write_key_table()
        context=patch.object(client.forge_item_model_alias, 'ADDITIONAL_ITEMS', set())
        context.start();self.addCleanup(context.stop)
        for name,value in [('ROOT',self.root),('EXPECTED_FILES',5),('EXPECTED_SHARED',2),('EXPECTED_REPLACEMENTS',1),('EXPECTED_MODEL_OVERRIDES',1),('EXPECTED_KEY_DEFAULTS',1),
                ('PIXELMON_SHA256',client.digest(self.pixel)),('PORT_SHA256',client.digest(self.port))]:
            context=patch.object(client,name,value);context.start();self.addCleanup(context.stop)

    @staticmethod
    def archive_bytes(files):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for name, data in files.items(): archive.writestr(name, data)
        return stream.getvalue()

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
        if hasattr(self,'key_table'):self.write_key_table()

    def write_key_table(self,**changed):
        table=dict(self.key_table,mods_lock_sha256=client.digest(self.root/'forge-client-lock.json'))
        table.update(changed)
        (self.root/'compat/client-keys/default-keys.json').write_text(json.dumps(table))

    def build(self):
        return client.build(self.server,self.extras,self.society,self.output)

    def assert_no_export(self):
        with self.assertRaises(ValueError):self.build()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.parent.exists())

    def test_real_build_places_resources_and_deduplicates_identical_shader(self):
        report=self.build()
        self.assertEqual(report['mod_jars'],5)
        with zipfile.ZipFile(self.output) as z:
            self.assertEqual(z.read('overrides/mods/shared.jar'),self.fixture_data['shared.jar'])
            self.assertEqual(z.read('overrides/resourcepacks/resource.zip'),self.fixture_data['resource.zip'])
            self.assertEqual(z.read('overrides/shaderpacks/shader.zip'),self.fixture_data['shader.zip'])
            self.assertNotIn('overrides/mods/resource.zip',z.namelist())
            self.assertEqual(z.namelist().count('overrides/shaderpacks/shader.zip'),1)
            self.assertIn('overrides/resourcepacks/PSA-Forge-Model-Compat.zip',z.namelist())
            config=json.loads(z.read('overrides/config/resourcepackoverrides.json'))
            self.assertEqual(config['default_packs'],['vanilla','file/PSA-Forge-Model-Compat.zip'])
            self.assertTrue(config['pack_overrides']['file/PSA-Forge-Model-Compat.zip']['required'])
            profile = json.loads(z.read('overrides/psa-forge-client-profile.json'))
            alias = client.forge_item_model_alias
            self.assertEqual(json.loads(z.read('overrides/kubejs/' + alias.TARGET)), {'parent': alias.PARENT})
            self.assertEqual(len(profile['item_model_aliases']), 1)
        self.assertFalse((self.server/'kubejs'/client.forge_item_model_alias.TARGET).exists())

    def test_moved_pixelmon_key_is_added_to_the_default_key_file_and_recorded(self):
        self.build()
        with zipfile.ZipFile(self.output) as z:
            lines=z.read('overrides/configureddefaults/options.txt').decode().splitlines()
            profile=json.loads(z.read('overrides/psa-forge-client-profile.json'))
        added='key_key.pokemonexternal:key.keyboard.semicolon:NONE'
        self.assertEqual(lines[2:5],['key_key.curios.open.desc:key.keyboard.g:NONE',added,'soundCategory_master:1.0'])
        self.assertEqual(profile['default_key_compatibility']['added'],[added])
        self.assertEqual(profile['default_key_compatibility']['table_sha256'],
            client.digest(self.root/'compat/client-keys/default-keys.json'))

    def test_key_table_made_for_another_set_of_mod_jars_fails_before_output(self):
        for name in ['pixelmon_sha256','port_sha256','mods_lock_sha256']:
            with self.subTest(name):
                self.write_key_table(**{name:'0'*64})
                self.assert_no_export()
        self.write_key_table()
        self.build()

    def test_moved_key_that_another_binding_already_uses_fails_before_output(self):
        self.key_table['moved'][0]['to']='key.keyboard.g';self.write_key_table()
        self.assert_no_export()

    def test_declared_coexistence_repairs_are_applied_to_the_client_and_must_match(self):
        village, loot, overlay = client.forge_village_compat, client.forge_loot_compat, client.forge_overlay_compat
        vanilla = self.root/'vanilla-data.jar'; vanilla.write_bytes(b'vanilla data fixture, never opened')
        radium = b'radium options fixture'
        added = {village.SPAWN_PATH: b'// start script fixture', 'kubejs/data/minecraft/loot_tables/chests/x.json': b'{}',
                 'kubejs/data/c/tags/items/stones.json': b'{}', overlay.LITHIUM_PATH: radium}
        receipts = {'village_compatibility': {'fixture': 'village'}, 'loot_compatibility': {'fixture': 'loot'},
                    'overlay_compatibility': {'fixture': 'overlay'}}
        seen = []
        def applier(key, paths):
            def apply(files, *arguments):
                seen.append((key, arguments[:2] if key != 'overlay_compatibility' else arguments[:2] + (arguments[2]('mods/shared.jar'),)))
                for path in paths: files[path] = added[path]
                return receipts[key]
            return apply
        (self.server/'.psa-forge-candidate.json').write_text(json.dumps(receipts))
        for path, data in added.items():
            target = self.server/path; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
        declared = lambda root, declaration: declaration
        patches = [patch.multiple(village, verify_staged=declared, apply_overrides=applier('village_compatibility', [village.SPAWN_PATH])),
                   patch.multiple(loot, verify_staged=declared, apply_overrides=applier('loot_compatibility', ['kubejs/data/minecraft/loot_tables/chests/x.json'])),
                   patch.multiple(overlay, verify_staged=declared, apply_overrides=applier('overlay_compatibility', ['kubejs/data/c/tags/items/stones.json', overlay.LITHIUM_PATH]))]
        for context in patches: context.start()
        try:
            with self.assertRaisesRegex(ValueError, 'vanilla data JAR'):
                client.build(self.server, self.extras, self.society, self.output)
            self.assertFalse(self.output.parent.exists())
            seen.clear()
            client.build(self.server, self.extras, self.society, self.output, vanilla_data=vanilla)
            self.assertEqual(seen, [('village_compatibility', (self.pixel,)), ('loot_compatibility', (self.pixel, vanilla)),
                                    ('overlay_compatibility', (self.pixel, self.port, self.fixture_data['shared.jar']))])
            with zipfile.ZipFile(self.output) as z:
                for path, data in added.items():
                    self.assertEqual(z.read('overrides/' + path), data)
                profile = json.loads(z.read('overrides/psa-forge-client-profile.json'))
                for key, receipt in receipts.items():
                    self.assertEqual(profile[key], receipt)
            self.output.unlink(); self.output.parent.rmdir()
            # The server must carry exactly the bytes this exporter derives.
            (self.server/overlay.LITHIUM_PATH).write_bytes(radium + b' changed')
            with self.assertRaisesRegex(ValueError, 'Radium configuration differ'):
                client.build(self.server, self.extras, self.society, self.output, vanilla_data=vanilla)
            (self.server/overlay.LITHIUM_PATH).write_bytes(radium)
            with patch.object(loot, 'apply_overrides', lambda files, *arguments: {'different': True}):
                with self.assertRaisesRegex(ValueError, 'differs from this exporter'):
                    client.build(self.server, self.extras, self.society, self.output, vanilla_data=vanilla)
            self.assertFalse(self.output.parent.exists())
        finally:
            for context in patches: context.stop()
        # A server that carries the start script without declaring it is refused by the real check.
        (self.server/'.psa-forge-candidate.json').write_text('{}')
        self.assert_no_export()

    def test_kubejs_mismatch_fails_before_output(self):
        (self.server/'kubejs/server_scripts/init.js').write_bytes(b'changed')
        self.assert_no_export()

    def test_export_includes_nonempty_additional_batch_and_profile_provenance(self):
        alias = client.forge_item_model_alias
        jar = self.server/alias.JAR
        model = 'assets/decorative_blocks/models/block/owned.json'
        data = b'{"elements":[]}'  # Packaging fixture only, never a game model.
        with zipfile.ZipFile(jar,'a') as archive:
            archive.writestr(model,data)
        for entry in self.files:
            if entry['path']==alias.JAR:
                entry['size']=jar.stat().st_size;entry['hashes']=self.hashes(jar.read_bytes())
        self.write_lock()
        specs=[]
        for name in ('owned_first','owned_second'):
            specs.append({'item':'decorative_blocks:'+name,'jar':alias.JAR,'jar_sha256':client.digest(jar),
                'target_path':'assets/decorative_blocks/models/item/'+name+'.json',
                'parent':'decorative_blocks:block/owned','resources':{model:hashlib.sha256(data).hexdigest()},
                'vanilla_dependencies':[]})
        (self.root/'compat/item-model-aliases.json').write_text(json.dumps(specs))
        with patch.object(alias,'ADDITIONAL_ITEMS',{s['item'] for s in specs}),patch.object(alias,'JAR_SHA256',client.digest(jar)):
            self.build()
        with zipfile.ZipFile(self.output) as archive:
            profile=json.loads(archive.read('overrides/psa-forge-client-profile.json'))
            self.assertEqual(len(profile['item_model_aliases']),3)
            for spec in specs:
                path='kubejs/'+spec['target_path']
                self.assertIn('overrides/'+path,archive.namelist())
                self.assertEqual(profile['overrides'][path],hashlib.sha256(archive.read('overrides/'+path)).hexdigest())
                receipt=next(r for r in profile['item_model_aliases'] if r['item']==spec['item'])
                self.assertEqual(receipt['vanilla_dependencies'],[])

    def test_extra_server_jar_fails_before_output(self):
        (self.server/'mods/extra.jar').write_bytes(b'extra')
        self.assert_no_export()

    def test_different_bundled_shader_fails_before_output(self):
        self.overrides['shaderpacks/shader.zip']=b'different';self.write_base()
        self.assert_no_export()

    def test_windows_collision_fails_before_output(self):
        self.overrides['resourcepacks/RESOURCE.zip']=self.archive_bytes({'fixture.txt':b'other'})
        self.write_base()
        with self.assertRaisesRegex(ValueError, 'case-colliding'):
            self.build()
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.parent.exists())

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

    def test_menu_fix_is_client_only_and_recorded_in_payload(self):
        menu = self.root/'menu-fixture.jar'
        menu.write_bytes(self.archive_bytes({'fixture.txt':b'archive fixture, never executed'}))
        before = {p.name: p.read_bytes() for p in (self.server/'mods').iterdir()}
        with patch.object(client, 'MENU_PATCH_SHA256', client.digest(menu)):
            report = client.build(self.server, self.extras, self.society, self.output, menu)
        self.assertEqual(report['mod_jars'], 6)
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.server/'mods').iterdir()})
        with zipfile.ZipFile(self.output) as archive:
            name = 'mods/' + client.MENU_PATCH_NAME
            self.assertEqual(archive.read('overrides/' + name), menu.read_bytes())
            profile = json.loads(archive.read('overrides/psa-forge-client-profile.json'))
            self.assertTrue(profile['client_menu_compatibility']['client_only'])
            self.assertEqual(profile['overrides'][name], client.digest(menu))

    def test_invalid_menu_fix_preserves_output_state(self):
        menu = self.root/'menu-fixture.jar'
        menu.write_bytes(b'unverified file')
        for source in [menu, self.root/'missing.jar']:
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'menu compatibility'):
                client.build(self.server, self.extras, self.society, self.output, source)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.parent.exists())

    def test_ali_fix_is_client_only_and_preserves_other_payloads(self):
        target = self.add_ali_target_fixture()
        ali = self.root/'ali-fixture.jar'
        ali.write_bytes(self.archive_bytes({'fixture.txt':b'packaging only; never executed'}))
        before = {p.name:p.read_bytes() for p in (self.server/'mods').iterdir()}
        with patch.multiple(client, ALI_PATCH_SHA256=client.digest(ali), ALI_TARGET_SHA256=client.digest(target),
                EXPECTED_FILES=len(self.files), EXPECTED_SHARED=sum(f['side']=='both' for f in self.files)):
            report = client.build(self.server, self.extras, self.society, self.output, ali_fix=ali)
        self.assertEqual(report['mod_jars'], 7)
        self.assertEqual(before, {p.name:p.read_bytes() for p in (self.server/'mods').iterdir()})
        with zipfile.ZipFile(self.output) as archive:
            name = 'mods/' + client.ALI_PATCH_NAME
            self.assertEqual(archive.read('overrides/' + name), ali.read_bytes())
            self.assertEqual(archive.read('overrides/mods/shared.jar'), self.fixture_data['shared.jar'])
            profile = json.loads(archive.read('overrides/psa-forge-client-profile.json'))
            self.assertTrue(profile['client_ali_compatibility']['client_only'])
            self.assertEqual(profile['overrides'][name], client.digest(ali))

    def test_invalid_missing_or_symlink_ali_fix_cannot_export(self):
        ali = self.root/'ali-fixture.jar';ali.write_bytes(b'unverified')
        for source in (ali, self.root/'missing.jar'):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'ALI compatibility'):
                client.build(self.server, self.extras, self.society, self.output, ali_fix=source)
        link = self.root/'ali-link.jar';link.symlink_to(ali)
        with patch.object(client, 'ALI_PATCH_SHA256', client.digest(ali)), self.assertRaisesRegex(ValueError, 'ALI compatibility'):
            client.build(self.server, self.extras, self.society, self.output, ali_fix=link)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.output.parent.exists())

    def add_ali_target_fixture(self):
        data = self.archive_bytes({'fixture.txt':b'ALI packaging target fixture, never executed'})
        target = self.server/client.ALI_TARGET_PATH;target.write_bytes(data)
        self.files.append({'path':client.ALI_TARGET_PATH,'kind':'mod','side':'both','project_id':99,'file_id':199,
            'size':len(data),'hashes':self.hashes(data),'url':'https://example.test/ali-fixture.jar'})
        self.write_lock();self.write_base()
        return target

    def test_ali_fix_without_target_is_refused_before_output(self):
        ali = self.root/'ali-fixture.jar';ali.write_bytes(b'owned packaging fixture')
        with patch.object(client, 'ALI_PATCH_SHA256', client.digest(ali)), self.assertRaisesRegex(ValueError, 'Pinned ALI target'):
            client.build(self.server,self.extras,self.society,self.output,ali_fix=ali)
        self.assertFalse(self.output.exists());self.assertFalse(self.output.parent.exists())

    def test_valid_lock_with_wrong_ali_target_is_refused(self):
        self.add_ali_target_fixture()
        ali = self.root/'ali-fixture.jar';ali.write_bytes(b'owned packaging fixture')
        with patch.multiple(client, ALI_PATCH_SHA256=client.digest(ali),
                EXPECTED_FILES=len(self.files), EXPECTED_SHARED=sum(f['side']=='both' for f in self.files)), self.assertRaisesRegex(ValueError, 'Pinned ALI target'):
            client.build(self.server,self.extras,self.society,self.output,ali_fix=ali)
        self.assertFalse(self.output.exists());self.assertFalse(self.output.parent.exists())

    def test_corrected_loot_resource_matches_staged_server(self):
        self.build()
        name = client.forge_datapack_compat.RESOURCE
        with zipfile.ZipFile(self.output) as archive:
            data = archive.read('overrides/'+name)
            self.assertEqual(data, (self.server/name).read_bytes())
            self.assertFalse(json.loads(data)['replace'])
            self.assertEqual(json.loads(data)['entries'], [])

    def test_changed_loot_input_even_with_relocked_archive_is_refused(self):
        self.overrides[client.forge_datapack_compat.RESOURCE] = b'{}'
        self.write_base()
        self.assert_no_export()

    def test_declared_missing_server_only_module_is_refused(self):
        (self.server/'.psa-forge-candidate.json').write_text(json.dumps({
            'datapack_sync_compatibility':client.forge_datapack_compat.module_receipt()}))
        self.assert_no_export()

    def test_verified_server_only_module_is_not_in_client_payload(self):
        helper = client.forge_datapack_compat
        target = self.server/helper.TARGET_PATH; target.write_bytes(self.archive_bytes({'fixture.txt':b'not a game mod'}))
        data = target.read_bytes()
        self.files.append({'path':helper.TARGET_PATH,'kind':'mod','side':'both','project_id':100,'file_id':200,
            'size':len(data),'hashes':self.hashes(data),'url':'https://example.test/serializer-fixture.jar'})
        module = self.server/helper.MODULE_PATH; module.write_bytes(b'authored module packaging fixture only')
        self.write_base()
        with patch.multiple(helper, MODULE_SHA256=helper.digest(module), TARGET_SHA256=helper.digest(target)), patch.multiple(
                client, EXPECTED_FILES=len(self.files), EXPECTED_SHARED=sum(f['side']=='both' for f in self.files)):
            declaration = helper.module_receipt()
            (self.server/'.psa-forge-candidate.json').write_text(json.dumps({'datapack_sync_compatibility':declaration}))
            self.build()
            with zipfile.ZipFile(self.output) as archive:
                self.assertNotIn('overrides/'+helper.MODULE_PATH, archive.namelist())
                profile = json.loads(archive.read('overrides/psa-forge-client-profile.json'))
                self.assertEqual(profile['server_datapack_sync_compatibility'], declaration)


if __name__=='__main__':unittest.main()
