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
