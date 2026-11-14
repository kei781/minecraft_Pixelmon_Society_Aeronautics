import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from psa_support.codex_client import CodexClient, DISABLED_FEATURES
from psa_support.models import Plan


class CodexBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.binary=self.root/'fake-codex';self.home=self.root/'auth';self.home.mkdir()
        self.client=CodexClient(self.binary,self.home,self.root/'work')

    def tearDown(self): self.tmp.cleanup()

    def fake(self,body):
        import sys
        self.binary.write_text('#!'+sys.executable+'\n'+body)
        self.binary.chmod(0o700)

    def test_environment_does_not_inherit_credentials(self):
        old=os.environ.get('DISCORD_BOT_TOKEN')
        os.environ['DISCORD_BOT_TOKEN']='test-only-sentinel'
        try:
            env=self.client.environment()
            self.assertNotIn('DISCORD_BOT_TOKEN',env)
            self.assertNotIn('OPENAI_API_KEY',env)
            self.assertNotIn('SSH_AUTH_SOCK',env)
            self.assertEqual(env['CODEX_HOME'],str(self.home))
        finally:
            if old is None:os.environ.pop('DISCORD_BOT_TOKEN',None)
            else:os.environ['DISCORD_BOT_TOKEN']=old

    def test_restrictive_command_flags(self):
        schema=self.root/'schema.json'
        cmd=self.client.command('model','untrusted $(touch no) quotes "',schema)
        self.assertIn('--ignore-user-config',cmd)
        self.assertIn('--strict-config',cmd)
        self.assertIn('--ephemeral',cmd)
        self.assertEqual(cmd[cmd.index('--sandbox')+1],'read-only')
        self.assertIn('approval_policy="never"',cmd)
        for feature in ('shell_tool','apps','plugins','hooks','browser_use','computer_use','multi_agent'):
            self.assertIn(feature,DISABLED_FEATURES)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',cmd)

    def test_real_subprocess_transport_and_schema(self):
        self.fake('''import sys,json,os
question=sys.stdin.read()
assert 'DISCORD_BOT_TOKEN' not in os.environ
assert '$(touch' in question
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':json.dumps({'queries':['stone_pickaxe']})}}))
print(json.dumps({'type':'turn.completed'}))
''')
        result=asyncio.run(self.client.parse(model='test',instructions='policy',input='$(touch /tmp/never-shell)',text_format=Plan))
        self.assertEqual(result.output_parsed.queries,['stone_pickaxe'])
        self.assertEqual(list(self.client.workdir.iterdir()),[])

    def test_tool_event_rejected(self):
        self.fake("print('{\"type\":\"item.started\",\"item\":{\"type\":\"command_execution\"}}')")
        with self.assertRaisesRegex(ValueError,'tool activity'):
            asyncio.run(self.client.parse(model='test',instructions='policy',input='q',text_format=Plan))

    def test_failure_does_not_return_success(self):
        self.fake('raise SystemExit(1)')
        with self.assertRaises(RuntimeError):
            asyncio.run(self.client.parse(model='test',instructions='policy',input='q',text_format=Plan))

    def test_cancellation_cleans_subprocess(self):
        pidfile=self.root/'pid'
        self.fake(f'import os,time\nopen({str(pidfile)!r},"w").write(str(os.getpid()))\ntime.sleep(60)')
        async def run():
            task=asyncio.create_task(self.client.parse(model='test',instructions='policy',input='q',text_format=Plan))
            for _ in range(100):
                if pidfile.exists():break
                await asyncio.sleep(.01)
            self.assertTrue(pidfile.exists());pid=int(pidfile.read_text())
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):await task
            with self.assertRaises(ProcessLookupError):os.kill(pid,0)
        asyncio.run(run())
