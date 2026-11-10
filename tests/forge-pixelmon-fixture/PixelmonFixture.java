package dev.psa.pixelmonfixture;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.pixelmonmod.pixelmon.api.pokemon.Pokemon;
import com.pixelmonmod.pixelmon.api.test.TestResult;
import com.pixelmonmod.pixelmon.api.test.UnitTest;
import com.pixelmonmod.pixelmon.battles.controller.BattleController;
import com.pixelmonmod.pixelmon.battles.controller.participants.WildPixelmonParticipant;
import com.pixelmonmod.pixelmon.entities.pixelmon.PixelmonEntity;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.event.RegisterCommandsEvent;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.event.server.ServerStoppingEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.loading.FMLPaths;
import org.slf4j.Logger;
import com.mojang.logging.LogUtils;

/** Test-only world context for original, unmodified upstream battle assertions. */
@Mod("psapixelmonfixture")
public final class PixelmonFixture {
    private static final Logger LOG = LogUtils.getLogger();
    private static Session session;
    private static boolean consumed;
    private static final Map<String, String> TESTS = Map.ofEntries(
        Map.entry("example.SplashTest", "splash_no_damage"),
        Map.entry("notexamples.ClangorousSoulblazeCorrectBoostAmountTest", "clangorous_soulblaze_correct_boost_amount"),
        Map.entry("notexamples.DancerTest", "dancer_copies_damage_dealing_dance_moves"),
        Map.entry("notexamples.HiddenPowerMaxMoveTypingTest", "hidden_power_max_move_typing"),
        Map.entry("notexamples.NonExtremeWeatherFailsDuringDeltaStreamTest", "non_extreme_weather_fails_during_delta_stream"),
        Map.entry("notexamples.ShedinjaHPDynamaxTest", "shedinja_hp_dynamax"),
        Map.entry("notexamples.ShellTrapTest", "shell_trap_damages_opponents_not_user"),
        Map.entry("notexamples.ShieldsDownRemovesHazardsTest", "shields_down_should_not_remove_hazards"),
        Map.entry("notexamples.SpammableDestinyBondTest", "spammable_destiny_bond"),
        Map.entry("notexamples.TypeTesting", "Normal doesn't damage ghost"));

    public PixelmonFixture() {
        MinecraftForge.EVENT_BUS.addListener(this::commands);
        MinecraftForge.EVENT_BUS.addListener(this::tick);
        MinecraftForge.EVENT_BUS.addListener(this::stopping);
    }

    private void commands(RegisterCommandsEvent event) {
        event.getDispatcher().register(Commands.literal("psa_pixelmon_hp_controls")
            .requires(source -> source.getEntity() == null && source.hasPermission(4))
            .executes(context -> {
                FixtureMixinPlugin.requireOwnedProfile();
                if (!context.getSource().getServer().isDedicatedServer()
                        || context.getSource().getServer().getPlayerCount() != 0)
                    throw new IllegalStateException("Dedicated disposable server without players required");
                try {
                    Path result = HitpointControls.run();
                    LOG.info("PSA_PIXELMON_HP_CONTROLS COMPLETE {}", result.getFileName());
                } catch (java.io.IOException failure) {
                    LOG.error("PSA_PIXELMON_HP_CONTROLS FAILED", failure);
                    throw new IllegalStateException("HP report I/O failed", failure);
                }
                return 1;
            }));
        event.getDispatcher().register(Commands.literal("psa_pixelmon_fixture")
            .requires(source -> source.getEntity() == null && source.hasPermission(4))
            .executes(context -> {
                var server = context.getSource().getServer();
                if (!server.isDedicatedServer() || server.getPlayerCount() != 0 || consumed)
                    throw new IllegalStateException("Fresh dedicated JVM, no players, one run only");
                final List<Method> methods;
                try {
                    FixtureMixinPlugin.requireOwnedProfile();
                    methods = discover(); // fail before any world mutation
                    var expectedTargets = new java.util.HashSet<String>();
                    for (String type : TESTS.keySet()) expectedTargets.add("com.pixelmonmod.pixelmon.api.test." + type);
                    FixtureMixinPlugin.requireApplied(expectedTargets);
                } catch (Throwable failure) {
                    rethrowFatal(failure);
                    LOG.error("PSA_PIXELMON_FIXTURE PREFLIGHT_REFUSED", failure);
                    throw new IllegalStateException("Fixture preflight failed", failure);
                }
                consumed = true;
                session = new Session(server.overworld());
                try { session.start(methods); }
                catch (Throwable failure) { rethrowFatal(failure); session.fail(failure); }
                context.getSource().sendSuccess(() -> Component.literal("PSA_PIXELMON_FIXTURE " + session.id), false);
                return 1;
            }));
    }

    private static List<Method> discover() throws ReflectiveOperationException {
        var result = new ArrayList<Method>();
        for (var entry : TESTS.entrySet()) {
            Class<?> type = Class.forName("com.pixelmonmod.pixelmon.api.test." + entry.getKey());
            var found = new ArrayList<Method>();
            for (Method method : type.getDeclaredMethods()) {
                UnitTest annotation = method.getAnnotation(UnitTest.class);
                // Match the native registry's eligibility filter before checking inventory.
                // SplashTest also annotates a parameterized example which native runTests skips.
                if (annotation == null || method.getParameterCount() != 0
                        || !Modifier.isStatic(method.getModifiers()) || method.getReturnType() != CompletableFuture.class)
                    continue;
                if (!entry.getValue().equals(annotation.value()) || !Modifier.isPublic(method.getModifiers()))
                    throw new IllegalStateException("Unexpected native test method: " + method.getName());
                found.add(method);
            }
            if (found.size() != 1) throw new IllegalStateException("Expected one native test per pinned class");
            result.add(found.get(0));
        }
        result.sort(java.util.Comparator.comparing(method -> method.getAnnotation(UnitTest.class).value()));
        if (result.size() != 10) throw new IllegalStateException("Expected exactly ten native tests");
        return result;
    }

    /** Only the ten pinned test classes call this; no battle rules or results change. */
    public static WildPixelmonParticipant participant(Pokemon[] pokemon) {
        if (session == null) return new WildPixelmonParticipant(pokemon);
        return session.createParticipant(pokemon);
    }

    private void tick(TickEvent.ServerTickEvent event) {
        if (event.phase == TickEvent.Phase.END && session != null && !session.closed) {
            try { session.poll(); }
            catch (Throwable failure) { rethrowFatal(failure); session.fail(failure); }
        }
    }

    private void stopping(ServerStoppingEvent event) {
        if (session != null && !session.closed) session.fail(new IllegalStateException("Server stopped during tests"));
    }

    private static void rethrowFatal(Throwable failure) {
        if (failure instanceof VirtualMachineError error) throw error;
        if (failure instanceof ThreadDeath death) throw death;
    }

    private static Throwable unwrap(Throwable failure) {
        while ((failure instanceof java.lang.reflect.InvocationTargetException
                || failure instanceof java.util.concurrent.CompletionException) && failure.getCause() != null)
            failure = failure.getCause();
        return failure;
    }

    private static final class Session {
        final String id = UUID.randomUUID().toString();
        final ServerLevel level;
        final long deadline = System.nanoTime() + 120_000_000_000L;
        final Map<String, CompletableFuture<?>> futures = new LinkedHashMap<>();
        final Map<String, JsonObject> results = new LinkedHashMap<>();
        // Use mapped vanilla owners for inherited methods during Forge reobfuscation.
        final List<net.minecraft.world.entity.Mob> actors = new ArrayList<>();
        final List<WildPixelmonParticipant> participants = new ArrayList<>();
        final List<BlockPos> floor = new ArrayList<>();
        final List<String> cleanupErrors = new ArrayList<>();
        final List<String> errors = new ArrayList<>();
        final List<JsonObject> joins = new ArrayList<>();
        List<Method> pendingMethods;
        final Path directory = FMLPaths.GAMEDIR.get().resolve("psa-pixelmon-fixture").resolve(id);
        int checkpoint;
        boolean forced, closed, cleaned, sceneReady;

        Session(ServerLevel level) { this.level = level; }

        void start(List<Method> methods) throws Exception {
            checkpoint("preparing");
            if (level.getForcedChunks().contains(0L)) throw new IllegalStateException("Scene chunk already forced");
            forced = true; // ownership recorded before requesting the ticket
            level.setChunkForced(0, 0, true);
            pendingMethods = List.copyOf(methods);
            checkpoint("waiting_for_chunk");
        }

        void launch(List<Method> methods) throws Exception {
            sceneReady = true;
            for (int x = 0; x < 16; x++) for (int z = 0; z < 16; z++)
                for (int y = 128; y < 160; y++)
                    if (!level.isEmptyBlock(new BlockPos(x, y, z)))
                        throw new IllegalStateException("Disposable fixture scene must be empty");
            for (int x = 0; x < 16; x++) for (int z = 0; z < 16; z++) {
                var position = new BlockPos(x, 128, z);
                floor.add(position);
                if (!level.setBlock(position, Blocks.STONE.defaultBlockState(), 3))
                    throw new IllegalStateException("Fixture floor rejected");
            }
            checkpoint("running");
            for (Method method : methods) {
                String name = method.getAnnotation(UnitTest.class).value();
                try {
                    Object nativeFuture = method.invoke(null);
                    if (!(nativeFuture instanceof CompletableFuture<?> future))
                        throw new IllegalStateException("Missing native future");
                    futures.put(name, future);
                } catch (Throwable failure) {
                    Throwable cause = unwrap(failure); rethrowFatal(cause);
                    LOG.error("PSA_PIXELMON_FIXTURE INVOCATION_FAILED " + name, cause);
                    var row = new JsonObject(); row.addProperty("status", "error");
                    row.addProperty("error", cause.toString()); results.put(name, row);
                    throw new IllegalStateException("Native test could not start: " + name, cause);
                }
            }
            checkpoint("running");
        }

        WildPixelmonParticipant createParticipant(Pokemon[] pokemon) {
            if (closed || !level.getServer().isSameThread() || pokemon.length == 0
                    || actors.size() + pokemon.length > 64)
                throw new IllegalStateException("Inactive/invalid fixture actor request");
            var entities = new PixelmonEntity[pokemon.length];
            for (int i = 0; i < pokemon.length; i++) {
                if (pokemon[i].getPixelmonEntity().isPresent())
                    throw new IllegalStateException("Refuse preexisting Pokemon entity");
                int slot = actors.size();
                net.minecraft.world.entity.Mob actor = pokemon[i].getOrCreatePixelmon(level, 0.75 + (slot % 8) * 1.8,
                    129, 0.75 + (slot / 8) * 1.8);
                if (actor == null || level.getEntity(actor.getUUID()) != null)
                    throw new IllegalStateException("Refuse missing/preexisting actor");
                actors.add(actor); // record identity before native join event
                checkpoint("actor_intent");
                actor.setNoAi(true); actor.setPersistenceRequired();
                boolean added = level.addFreshEntity(actor);
                var join = new JsonObject();
                join.addProperty("added", added);
                join.addProperty("entity_lookup_matches", level.getEntity(actor.getUUID()) == actor);
                join.addProperty("pokemon_lookup_matches", pokemon[i].getPixelmonEntity().orElse(null) == actor);
                join.addProperty("pokemon_uuid_matches", pokemon[i].getUUID().equals(actor.getUUID()));
                join.addProperty("server_identity_matches", net.minecraftforge.server.ServerLifecycleHooks.getCurrentServer() == level.getServer());
                join.addProperty("removed", actor.isRemoved());
                joins.add(join); checkpoint("actor_join");
                if (!added || !join.get("entity_lookup_matches").getAsBoolean()
                        || !join.get("pokemon_lookup_matches").getAsBoolean())
                    throw new IllegalStateException("Native fixture spawn/binding rejected");
                entities[i] = (PixelmonEntity) actor;
            }
            var participant = new WildPixelmonParticipant(entities);
            participants.add(participant);
            return participant;
        }

        void poll() {
            if (pendingMethods != null) {
                if (System.nanoTime() > deadline) throw new IllegalStateException("Scene chunk readiness timeout");
                if (!level.areEntitiesLoaded(0L) || !level.isPositionEntityTicking(new BlockPos(8, 129, 8))) return;
                var methods = pendingMethods; pendingMethods = null;
                LOG.info("PSA_PIXELMON_FIXTURE SCENE_READY {}", id);
                try { launch(methods); }
                catch (Exception failure) { throw new IllegalStateException("Native suite launch failed", failure); }
            }
            collectResults();
            if (results.size() == 10) finish();
            else if (System.nanoTime() > deadline) {
                for (String name : TESTS.values()) if (!results.containsKey(name)) {
                    var row = new JsonObject(); row.addProperty("status", "timeout"); results.put(name, row);
                }
                finish();
            }
        }

        void collectResults() {
            for (var entry : futures.entrySet()) {
                if (results.containsKey(entry.getKey()) || !entry.getValue().isDone()) continue;
                var row = new JsonObject();
                try {
                    Object value = entry.getValue().join();
                    if (!(value instanceof TestResult nativeResult)) throw new IllegalStateException("Invalid native result");
                    row.addProperty("status", nativeResult.isSuccess() ? "success" : "failure");
                    row.addProperty("reason", nativeResult.getReason());
                    if (nativeResult.getError() != null) row.addProperty("error", nativeResult.getError().toString());
                } catch (Throwable failure) {
                    Throwable cause = unwrap(failure); rethrowFatal(cause);
                    LOG.error("PSA_PIXELMON_FIXTURE FUTURE_FAILED " + entry.getKey(), cause);
                    row.addProperty("status", "error"); row.addProperty("error", cause.toString());
                }
                results.put(entry.getKey(), row);
                LOG.info("PSA_PIXELMON_FIXTURE RESULT {} {}", entry.getKey(), row);
            }
        }

        void fail(Throwable failure) {
            errors.add(failure.toString()); LOG.error("PSA_PIXELMON_FIXTURE FAILED", failure); finish();
        }

        void finish() {
            if (closed) return;
            closed = true;
            collectResults(); // retain native results completed before an external abort
            for (String name : TESTS.values()) if (!results.containsKey(name)) {
                var row = new JsonObject();
                row.addProperty("status", futures.containsKey(name) ? "aborted" : "not_started");
                results.put(name, row);
            }
            Set<BattleController> battles = Collections.newSetFromMap(new IdentityHashMap<>());
            for (var participant : participants) if (participant.bc != null) battles.add(participant.bc);
            for (var battle : battles) try {
                if (!battle.battleEnded) battle.endBattleWithoutXP();
                if (!battle.battleEnded) throw new IllegalStateException("Owned battle survived cleanup");
            }
                catch (Throwable failure) { rethrowFatal(failure); cleanupErrors.add(failure.toString()); }
            for (var actor : actors) try {
                // Our exact constructed reference remains owned even before tracking starts.
                // A UUID lookup can be absent while an accepted entity is waiting for its chunk.
                if (!actor.isRemoved()) actor.discard();
                if (!actor.isRemoved())
                    throw new IllegalStateException("Owned actor survived cleanup");
            } catch (Throwable failure) { rethrowFatal(failure); cleanupErrors.add(failure.toString()); }
            for (var position : floor) try {
                if (level.getBlockState(position).is(Blocks.STONE)) {
                    level.setBlock(position, Blocks.AIR.defaultBlockState(), 3);
                    if (!level.isEmptyBlock(position)) throw new IllegalStateException("Fixture floor survived cleanup");
                } else if (!level.isEmptyBlock(position)) throw new IllegalStateException("Fixture floor unexpectedly changed");
            } catch (Throwable failure) { rethrowFatal(failure); cleanupErrors.add(failure.toString()); }
            if (forced) try {
                level.setChunkForced(0, 0, false);
                if (level.getForcedChunks().contains(0L)) throw new IllegalStateException("Fixture ticket survived cleanup");
            } catch (Throwable failure) { rethrowFatal(failure); cleanupErrors.add(failure.toString()); }
            cleaned = cleanupErrors.isEmpty();
            checkpoint("finished");
            LOG.info("PSA_PIXELMON_FIXTURE FINISHED {} cleanup={} pass={}", id, cleaned, passed());
        }

        boolean passed() {
            return closed && cleaned && errors.isEmpty() && results.size() == 10
                && sceneReady && !actors.isEmpty() && !participants.isEmpty()
                && results.values().stream().allMatch(row -> "success".equals(row.get("status").getAsString()));
        }

        void checkpoint(String phase) {
            var report = new JsonObject(); report.addProperty("run", id);
            report.addProperty("phase", phase); report.addProperty("time", Instant.now().toString());
            report.addProperty("scope", "Original ten test methods/assertions; world-backed participants; no player authentication tested");
            report.addProperty("pass", passed()); report.addProperty("cleanup_complete", cleaned);
            report.addProperty("closed", closed); report.addProperty("forced_chunk_owned", forced);
            report.addProperty("scene_ready", sceneReady);
            report.addProperty("live_owned_actor_count", actors.stream().filter(actor -> !actor.isRemoved()).count());
            report.addProperty("participants", participants.size()); report.addProperty("actor_count", actors.size());
            var identities = new JsonArray(); for (var actor : actors) identities.add(actor.getUUID().toString());
            report.add("owned_entities", identities);
            report.add("joins", new GsonBuilder().create().toJsonTree(joins));
            report.add("results", new GsonBuilder().create().toJsonTree(results));
            report.add("errors", new GsonBuilder().create().toJsonTree(errors));
            report.add("cleanup_errors", new GsonBuilder().create().toJsonTree(cleanupErrors));
            try {
                Files.createDirectories(directory);
                Files.writeString(directory.resolve(String.format("%04d-%s.json", checkpoint++, phase)),
                    new GsonBuilder().setPrettyPrinting().create().toJson(report) + "\n",
                    StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            } catch (java.io.IOException failure) {
                throw new IllegalStateException("Fixture evidence I/O failed", failure);
            }
        }
    }
}
