# Pixelmon base attribute advance implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline. The user requested continuous execution; independent review uses the existing Claude review loop.

**Goal:** Reduce repeated base-attribute cursor transitions while preserving original shader completion and exact output.

**Architecture:** A separately gated BufferBuilder mixin validates and applies the same cursor state as six Embeddium transitions. The original native writer and endVertex hooks remain in charge of bytes and shader completion. Unexpected layouts or observed method bodies retain the existing path.

**Tech stack:** Java 17, Forge 47.4.20, Pixelmon 9.2.3, Oculus 1.8.0, Embeddium 0.3.31, Mixin 0.8.5, Python 3.9+.

**Spec:** ../specs/2026-11-16-pixelmon-advance-design.md

## Global constraints

- Preserve 24-chunk view and all shader/model/animation quality settings.
- Both startup flags are required; default remains OFF.
- Preserve all existing endVertex hooks, tangent arithmetic and native-write guards.
- Never distribute upstream classes or raw profiles, coordinates, account/server information.
- Original and running playtest instances remain untouched; use auto-exit QA only.
- PR is stacked on #22; merge and deployment are outside this request.

## Review focus

- Other BufferBuilder transformations: reject an unexpected observed nextElement body.
- Fixed color and partial vertices: no cursor or byte mutation on rejection.
- Builder format changes/reuse: stale plans must not corrupt a different layout.
- Alternating original/candidate vertices and buffer growth: exact shader attributes and state.
- Opt-out: no advance interface or mixin transformation without both flags.

### Task 1: Gate and compatibility checks

Files: RenderCompatPlugin.java, new AdvanceCompatibility.java, PixelmonVertexEncodingTest.java, new PixelmonAdvanceCompatibilityTest.java, build_pixelmon_render.py.

Interfaces: `AdvanceCompatibility.supports(ClassNode): boolean`; `disableUnsupported(ClassNode): void` rewrites only the authored `psa$tryAdvanceEntityBase(): boolean` to return false if unsupported.

- [x] Add the two-flag matrix to the real Java test; build --test must fail on the existing plugin.
- [x] Add a bytecode test against the pinned real Embeddium method, plus injected foreign-hook/missing-method rejection; run RED before implementing the guard.
- [x] Implement gating and the normalized structural hash guard; run Java and Python build checks GREEN.
- [x] Commit the tested gate, helper and tests.

### Task 2: State collapse and actual Forge invariants

Files: new FastEntityVertexAdvance.java, new EntityAdvanceMixin.java, EntityBufferMixin.java, mixin config, PixelmonRenderProbe.java.

Interfaces: `FastEntityVertexAdvance.psa$tryAdvanceEntityBase(): boolean` returns false without mutation when unsupported. EntityBufferMixin falls back to six original calls.

- [x] Extend the QA probe with real original-six-versus-candidate state comparison and opt-out checks. Run it with the old candidate and observe RED.
- [x] Implement validated transition planning and cursor update; register low-priority mixin; run probe GREEN with both flags.
- [x] Cover rejected/mixed/reused builders, TRIANGLES/QUADS extended-byte equality and growth in the probe.
- [x] Run the same JAR with advance OFF and all flags OFF; run alternating-order CPU microbenchmark for both enabled cases.
- [x] Commit implementation and probe after meaningful checks pass.

### Task 3: Evidence, CI, PR and review

Files: docs/pixelmon-render-performance.md, sanitized evidence JSON, build receipt metadata as appropriate.

- [ ] Record exact candidate hash, commands, kernel results, baseline sandbox limits and unverified world/visual scope.
- [ ] Run appropriate Python checks and full CI; inspect failures rather than hiding existing Windows symlink restrictions.
- [ ] Push feature branch; create stacked draft PR targeting perf/pixelmon-render-pipeline, refs #21 and #22.
- [ ] Run independent latest Claude Opus review/fixes/re-review until latest HEAD clean and all threads resolved (max 8 rounds).
- [ ] Verify final head, CI and review state; leave original/playtest untouched and report remaining acceptance.
