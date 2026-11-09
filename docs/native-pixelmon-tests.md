# Headless native Pixelmon battle tests

The pinned Pixelmon 9.2.3 binary already contains ten eligible native battle
tests. Its console `battletests` command needs no player or graphical client.
Stock integrated and Pixelmon-only controls both logged seven successes,
two failures and one unfinished test. An unfinished suite is not a pass.
The stock fixtures create virtual participants without world entities;
null entity exceptions must be separated from gameplay failures.

The initial world-backed diagnostic produced the same ten native results in
both Pixelmon-only and full 313-production-mod profiles: eight successes,
two failures, zero unfinished tests and zero logged null-pointer exceptions.
The full run took 0.96 seconds from fixture start through cleanup, excluding
server boot. Each run owned 31 native actors and finished with zero live
owned actors, floor and ticket cleanup confirmed. The suite remains failed:
Shedinja Dynamax HP and Minior entry-hazard assertions need further diagnosis.
This comparison is evidence against a new failure introduced by this mod
combination for these ten assertions, not a general compatibility guarantee.
See `evidence/pixelmon-world-fixture-runtime.json` for exact artifacts/results.
After independent review, the transformation gate and interrupted-result
inventory were strengthened. The 26,100-byte diagnostic with SHA256
`861b616c6efcfba7dd56b9fd45b9abd212516b5efa2e6b2ce3ac70aed6303489`
produced eight successes/two failures in the full profile, but six successes/
four failures in its latest Pixelmon-only run. Dancer and Shell Trap also
failed in that latest isolated sample. This variation needs further diagnosis;
the earlier matching samples do not establish repeatability. Both current
runs finished with zero live owned actors and zero logged null-pointer errors.
Actual before/after boot and scene-failure controls are recorded in
`evidence/pixelmon-fixture-review-regressions.json`.

`tests/forge-pixelmon-fixture` is a separate diagnostic, excluded from player
exports. It redirects fourteen constructor sites in the ten pinned test
classes to native entity-backed participants using the same Pokemon objects.
Only those participant-construction sites change; original assertions,
battle rules, remaining test logic and native futures are retained.
This is an adapted fixture run, distinct from the stock command.
It invokes the eligible annotated methods with the native registry's static,
zero-argument, exact-CompletableFuture eligibility filter. SplashTest's
parameterized annotated example is intentionally ineligible.

Build with the prepared pinned Forge mapped workspace and Java 17:

```sh
gradle --offline --no-daemon --max-workers=2 -p /path/to/prepared-forge-workspace \
  -I /path/to/repository/tools/forge-pixelmon-fixture.gradle \
  -PpsaPixelmonFixtureSource=/path/to/repository/tests/forge-pixelmon-fixture \
  -PpsaPixelmonJar=/path/to/Pixelmon-1.20.1-9.2.3-universal.jar \
  reobfPsaPixelmonFixtureJar
python3 /path/to/repository/tools/forge_resources.py canonical-jar \
  /path/to/prepared-forge-workspace/build/libs/psa-pixelmon-fixture-0.1.jar \
  /path/to/fresh-diagnostic.jar
```

Use only a fresh, dedicated, disposable profile, never an existing play world.
The profile's working directory must contain `.psa-pixelmon-fixture` with the
exact content `psa-disposable-pixelmon-fixture-v1` followed by a newline.
The JVM must opt in with `-Dpsa.pixelmonFixture=true`. Exact `require` and
`allow` counts always constrain the fourteen fixture constructor sites.
The optional global `-Dmixin.debug.countInjections=true` worked in the
Pixelmon-only control, but causes an unrelated optional Canary/Lithium
injection expectation to abort the full pack's boot. Keep that global debug
flag off in full-pack runs; the fixture's own strict counts still apply.
The source archive hash is enforced both during build and before mixing.
After class discovery the command also requires all ten transformations to
have completed, independently of the boot-time plugin check. A marker added
after a skipped Mixin configuration cannot turn a stock run into an adapted
run. Passing also requires actual fixture actors and participants.
Minecraft 1.20.1 / Forge 47.4.20 / Pixelmon 9.2.3 are exact dependencies.

Keep authentication enabled, RCON disabled and the diagnostic server bound to
localhost. No player is required or allowed when starting the fixture run.
From its console execute `psa_pixelmon_fixture` once per fresh JVM. The scene
requires an empty 16 by 16 area above y=128 in chunk 0,0; it owns a temporary
floor, chunk ticket and at most 64 native Pokemon actors. It waits for native
entity loading and ticking readiness before creating the scene. Merely adding
a chunk ticket is insufficient: an accepted entity can still be absent from
UUID lookup until its chunk begins tracking. Cleanup therefore removes each
exact owned object reference even if that lookup is not ready. The actors have
world AI disabled; scripted native battle logic and assertions are retained.
They are not invulnerable and no game exception or failed assertion is masked.

Read the unique `psa-pixelmon-fixture/<run>/*-finished.json` after the
`PSA_PIXELMON_FIXTURE FINISHED` log line. It preserves each native success,
failure, exceptional result or a 120-second deadline measured from session
creation, including chunk readiness. Invocations which cannot start are
errors and stop the run. Unstarted and interrupted tests are retained as
`not_started` and `aborted`, respectively. Passing requires all ten successes, no
runner errors and successful cleanup of owned battle/entity/floor/ticket
objects. Evidence I/O failure must not be treated as completion. Native logs
remain available for full exception details. Stop the dedicated server
normally after collecting the result; quarantine an interrupted profile
rather than reusing it. No player saves or accounts belong in this profile.

These tests cover the original battle assertions. They do not verify client
rendering, survival capture costs, player input, farming/economy, flight or
six authenticated players. Those have separate validation records and gates.

Development controls are preserved separately: the first full run with a
global Mixin debug flag aborted boot; the initial runner rejected an
ineligible parameterized example; an inherited-method remapping error and
an unready chunk were corrected in the diagnostic. The old unready-chunk
run's cleanup flag is not accepted as proof because the earlier cleanup
relied on UUID lookup. Those disposable profiles are quarantined and stopped
normally. No production game code was changed by these controls.
