package dev.psa.codecprobe;

import com.pixelmonmod.api.pokemon.PokemonSpecificationProxy;
import com.pixelmonmod.pixelmon.api.config.PixelmonConfigProxy;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.level.GameRules;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.event.lifecycle.FMLLoadCompleteEvent;
import net.neoforged.neoforge.common.NeoForge;
import net.neoforged.neoforge.event.server.ServerStartedEvent;

/** Local-only test mod: exercises actual entity insertion and Pixelmon handlers. */
@Mod("psa_mobs_probe")
public final class MobCoexistenceProbe {
    public MobCoexistenceProbe(IEventBus bus) {
        bus.addListener(this::loaded);
        NeoForge.EVENT_BUS.addListener(this::started);
    }

    private void loaded(FMLLoadCompleteEvent event) {
        var config = PixelmonConfigProxy.getEntity();
        if (!config.isAllowVanillaMobs()
            || !config.isAllowCaptureOutsideBattle().contains("minecraft:overworld")
            || !config.isEngagePlayerByPokeBall() || !config.isEnableWildAggression()
            || config.isCanPokemonBeHit() || config.isDisabledNonPlayerMovement()) {
            throw new AssertionError("Minimal entity config did not preserve the other Pixelmon defaults");
        }
        System.out.println("PSA_MOBS_CONFIG PASS: allow-vanilla-mobs=true; other entity defaults preserved");
    }

    private void started(ServerStartedEvent event) {
        var server = event.getServer();
        var level = server.overworld();
        boolean preserved = Boolean.parseBoolean(System.getProperty("psa.expectedMobsPreserved", "false"));
        if (!level.getGameRules().getBoolean(GameRules.RULE_DOMOBSPAWNING)) {
            throw new AssertionError("Pixelmon did not enable the world's doMobSpawning rule");
        }
        for (EntityType<?> type : new EntityType<?>[] { EntityType.COW, EntityType.CHICKEN,
                EntityType.PIG, EntityType.SHEEP, EntityType.ZOMBIE }) {
            Entity entity = type.create(level);
            if (entity == null) throw new AssertionError("Could not create " + type);
            entity.setPos(0.5, 100.0, 0.5);
            boolean accepted = level.addFreshEntity(entity);
            System.out.println("PSA_MOBS_INSERT " + BuiltInRegistries.ENTITY_TYPE.getKey(type) + "=" + accepted);
            if (accepted != preserved) {
                throw new AssertionError("Unexpected vanilla entity insertion result for " + type);
            }
            entity.discard();
        }
        var pokemon = PokemonSpecificationProxy.create("pikachu lvl:5").get().create(level);
        pokemon.setPos(0.5, 100.0, 0.5);
        if (!level.addFreshEntity(pokemon)) throw new AssertionError("Pixelmon entity was blocked");
        pokemon.discard();
        System.out.println("PSA_MOBS_PROBE PASS: preserved=" + preserved + "; Pixelmon entity insertion accepted");
        if (Boolean.getBoolean("psa.probe.autoStop")) server.halt(false);
    }
}
