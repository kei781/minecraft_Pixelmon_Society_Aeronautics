"""Use official Codex CLI with ChatGPT sign-in; never read or proxy OAuth tokens."""
from __future__ import annotations
import asyncio
import json
import os
import signal
import tempfile
from pathlib import Path
from types import SimpleNamespace

DISABLED_FEATURES = (
    'shell_tool', 'apps', 'plugins', 'hooks', 'browser_use', 'browser_use_external',
    'computer_use', 'multi_agent', 'view_image', 'image_generation', 'shell_snapshot',
    'skill_search', 'tool_suggest', 'workspace_dependencies', 'goals', 'sleep_tool',
)


class CodexClient:
    def __init__(self, binary: Path, home: Path, workdir: Path):
        self.binary, self.home, self.workdir = binary, home, workdir
        self.responses = self
        self.workdir.mkdir(parents=True,exist_ok=True,mode=0o700)

    def command(self, model, instructions, schema):
        args = [str(self.binary), 'exec', '--ignore-user-config', '--strict-config',
                '--ephemeral', '--skip-git-repo-check', '--sandbox', 'read-only',
                '-C', str(schema.parent), '--model', model, '--json', '--color', 'never',
                '--output-schema',str(schema)]
        for feature in DISABLED_FEATURES:
            args += ['--disable',feature]
        for setting in ('web_search="disabled"', 'skills.bundled.enabled=false',
                        'skills.include_instructions=false', 'approval_policy="never"',
                        'model_reasoning_effort="low"', 'check_for_update_on_startup=false',
                        'feedback.enabled=false', 'analytics.enabled=false'):
            args += ['-c',setting]
        args += ['-c','developer_instructions='+json.dumps(instructions,ensure_ascii=False), '-']
        return args

    def environment(self):
        # Never inherit bot token, API keys, SSH agent, proxies, or caller-specific Codex instructions.
        return {'PATH':'/usr/bin:/bin', 'HOME':str(self.home), 'CODEX_HOME':str(self.home),
                'LANG':'C.UTF-8', 'TERM':'dumb'}

    async def parse(self, *, model, instructions, input, text_format, **unused):
        with tempfile.TemporaryDirectory(prefix='inquiry-',dir=self.workdir) as temp:
            schema = Path(temp)/'answer.schema.json'
            schema.write_text(json.dumps(text_format.model_json_schema(),ensure_ascii=False))
            process = await asyncio.create_subprocess_exec(
                *self.command(model,instructions,schema),
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,env=self.environment(),start_new_session=True)
            try:
                output, _ = await asyncio.wait_for(process.communicate(input.encode()),timeout=150)
            except BaseException:
                try: os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                await process.wait()
                raise
            if process.returncode:
                raise RuntimeError('Codex sign-in, quota, or execution failure')
            if len(output)>1_000_000:
                raise ValueError('Codex output exceeds inquiry limit')
            answer, completed = None, False
            for line in output.splitlines():
                event = json.loads(line)
                if event.get('type') in ('error','turn.failed'):
                    raise RuntimeError('Codex turn failed')
                item=event.get('item',{})
                if item and item.get('type') not in ('agent_message','reasoning'):
                    raise ValueError('Unexpected tool activity in inquiry-only Codex run')
                if event.get('type')=='item.completed' and item.get('type')=='agent_message':
                    answer=item.get('text')
                if event.get('type')=='turn.completed': completed=True
            if not completed or answer is None:
                raise ValueError('Codex response did not complete')
            return SimpleNamespace(output_parsed=text_format.model_validate_json(answer))
