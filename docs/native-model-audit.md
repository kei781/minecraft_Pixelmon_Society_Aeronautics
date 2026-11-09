# Native model lookup audit

`tests/forge-model-audit` is a disposable client diagnostic, excluded from the
production exporter. It requires the pinned Minecraft 1.20.1 / Forge 47.4.20.
Enable it only in the owned QA instance with `-Dpsa.modelAudit=true`.

After the resource bake and loading overlay finish, it queries at most 128
registered non-vanilla items per client tick using each original default stack
and `ItemRenderer.getModel(stack, null, null, 0)`. It records missing-model
sentinels, exceptions and unexpected empty/different default stacks separately.
The sorted catalog digest supports comparing the same inventory across reloads.
Each bake produces one new UUID-named report under `psa-model-audit/`, followed
by `PSA_MODEL_AUDIT COMPLETE` in the log. Read the report after that completion
line. There is no continuously replaced checkpoint or network acknowledgement.
Version 0.2 logs each current ID at debug level, records nonfatal throwables as
lookup errors, and rethrows VM/ThreadDeath failures. A report I/O error logs
`FAILED` with the full partial result, emits no `COMPLETE`, and stops that
generation's audit. It does not change the separate render probe's strict
checkpoint failure behavior.

This is model lookup with no world/player context. It does not prove textures,
actual rendering, native custom renderers, placement, interaction or gameplay.
Exceptions and context-dependent models require separate investigation; a
missing JSON path alone is not a missing-model verdict.

`tools/forge_item_model_alias.py` adds the missing Decorative Blocks tool name
as a client-only KubeJS asset referring to its original `blockstate_copy_tool`
model. The original JAR, model and PNG hashes are pinned. Another supplied
target model or a replaced parent/texture rejects export before output creation.
No original script or server file changes. Native verification is tracked in
the evidence files, separately from packaging/source checks.

The collision guard also checks resource-pack ZIPs/folders supplied as base
overrides and nested Forge JarJar archives. An invalid ZIP or excessive nesting
rejects export rather than silently skipping inspection.

`tests/java/MinecraftQaControl.java` is a local JDK Attach API helper for the
deliberately opted-in QA JVM. Its only actions are `status`, `reload`, and
`stop`; it requires `psa.modelAudit=true`, the PSA profile marker, and the exact
pinned Minecraft methods. Actions execute through Minecraft's own executor.
Resource reload completion means its native future completed; confirm the
separate audit `COMPLETE` marker too. `stop_requested` must be followed by
verification that the actual game ended normally. This helper does not belong
in `mods/`, has no arbitrary evaluation action, does not redefine classes, and
does not change authentication or input. Its reports use unique filenames under
`psa-qa-control/`.

Build the helper from the repository source and committed agent manifest:

```sh
python3 tools/build_minecraft_qa_control.py --java-home /path/to/jdk17 --output /path/to/fresh/qa-control.jar
/path/to/jdk17/bin/java --add-modules jdk.attach -cp /path/to/fresh/qa-control.jar dev.psa.qacontrol.MinecraftQaControl PID reload
```

The recipe rejects an existing output or a destination under `mods/`. The
actual 0.2 runtime helper is 3,833 bytes, SHA256
`b6ffd918acf0b00f9c6253e55ec320108f94d421597598fbbefc78f427bc1637`;
rebuilding with Java 17.0.21 produced identical bytes. Source/manifest hashes
and actual reload control IDs are in
`evidence/minecraft-qa-control-build-and-runtime.json`.

The actual Mac trial went from 22 to 21 missing-model sentinels with the same
17,239-item catalog. All 53 Decorative Blocks dropped-item render returns,
model masks and cleanup then passed on the authenticated server. Remaining
missing models, hand/inventory pixels, placement and use are still open.
