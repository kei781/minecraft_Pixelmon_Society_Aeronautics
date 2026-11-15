# Pixelmon entity vertex fast path implementation plan

> **For agentic workers:** Execute inline with superpowers:executing-plans. Independent review uses the explicitly requested claude-review-loop. Continue the user's authorized issue, implementation, PR and review work.

**Goal:** Reduce Pixelmon/Oculus CPU vertex submission overhead while preserving terrain distance, model detail, animation and shader output.

**Architecture:** Add a separate client compatibility mod for the pinned Pixelmon 9.2.3 / Oculus 1.8.0 / Embeddium 0.3.31 stack. Redirect only Pixelmon NormalizedFace's complete vertex submission. A guarded BufferBuilder adapter writes the same base attributes with native stores, advances the existing six attribute elements, then invokes the existing endVertex, including Oculus's entity IDs, tangent and midpoint processing. Unsupported formats/consumers retain the original call.

**Tech Stack:** Java 17, Forge 47, Sponge Mixin 0.8.5, LWJGL 3.3.1, Python unittest.

**Spec:** Issue #21 and user quality-preservation instruction in this chat.

## Global constraints

- Preserve render distance 24, smooth normals, model/animation detail, materials and shadows.
- Do not re-enable Pixelmon's unsafe fixed-stride vertex-copy cache.
- Do not skip Iris tangent, midpoint, entity-ID, buffer-growth or endVertex processing.
- Restrict the path to the exact supported extended entity format at a fresh vertex boundary, writable little-endian direct buffers and sufficient bounds; otherwise fall back before mutation.
- Ship only authored source/classes, no upstream binaries/models, raw profiles, credentials or server details.
- Separate encoding tests, loader integration and observed game FPS; no unsupported FPS promise.
- No live installation, server deployment or merge is implied by a reviewable PR.

## Review focus

- Normal clamp, color truncation, UV/light/overlay and non-finite float byte behavior must match the real original Minecraft consumer.
- End-of-buffer, heap/read-only/wrong-endian buffers must reject the fast path without writes.
- Vertex state advancement must leave Iris's extra-attribute hooks intact for triangles and quads.
- Missing/different dependencies and wrapped consumers must preserve original behavior.
- Build failures or changed inputs must not overwrite existing output or an installed mods directory.

### Task 1: exact vertex encoding and guarded client adapter

- [x] Write a Java comparison harness using the real pinned Minecraft BufferVertexConsumer as the independent reference. Test random and boundary attributes, guard bytes and buffer rejection before writes.
- [x] Run it first and observe the missing encoder failure.
- [x] Implement NativeEntityVertex and two narrowly scoped mixins plus client metadata. Keep Iris completion hooks and original fallback.
- [x] Compile against local pinned libraries; run byte comparisons and a separately labeled microbenchmark.
- [x] Add a build controller with pinned input hashes, fresh output guards and deterministic authored-only JAR packaging; cover rejection and packaging behavior with Python tests.

### Task 2: reproducibility, evidence and independent PR review

- [ ] Record sampled live baseline, code assumptions, test commands, bounds and remaining real-loader/FPS validation.
- [ ] Run full existing tests and focused new tests. Windows baseline has 17 existing symlink-privilege errors; the LF clone removes the original CRLF hash failure. Run the full suite in Linux CI too.
- [ ] Open a draft PR if real-loader or performance validation remains outstanding; link issue #21 without claiming a measured game improvement.
- [ ] Review latest HEAD with independent Claude Opus, fix valid findings and repeat until no unresolved threads, recording actual model and test limits.
- [ ] Attach PR and report issue, PR, checks and any remaining acceptance work to the user.
