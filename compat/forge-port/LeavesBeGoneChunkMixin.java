package dev.psa.compat;

import net.minecraft.world.level.chunk.LevelChunk;
import net.minecraft.world.ticks.LevelChunkTicks;
import net.minecraftforge.fml.ModList;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Initialize the optional leaf ticker on Sable's full-constructor chunks. */
@Mixin(LevelChunk.class)
public abstract class LeavesBeGoneChunkMixin {
    @Inject(method = "<init>(Lnet/minecraft/world/level/Level;Lnet/minecraft/world/level/ChunkPos;"
            + "Lnet/minecraft/world/level/chunk/UpgradeData;Lnet/minecraft/world/ticks/LevelChunkTicks;"
            + "Lnet/minecraft/world/ticks/LevelChunkTicks;J[Lnet/minecraft/world/level/chunk/LevelChunkSection;"
            + "Lnet/minecraft/world/level/chunk/LevelChunk$PostLoadProcessor;"
            + "Lnet/minecraft/world/level/levelgen/blending/BlendingData;)V", at = @At("RETURN"))
    private void psa$initializeLeafTicker(CallbackInfo callback) {
        if (!ModList.get().isLoaded("leavesbegone")) {
            return;
        }
        // Leaves Be Gone 8.0.0 initializes this field only in two shorter
        // constructors. All objects here are newly constructed; never reset
        // the queue of a loaded or ticking chunk. Its shorter constructors
        // retain their normal subsequent initialization/deserialization.
        try {
            Class<?> ticker = Class.forName("fuzs.leavesbegone.world.level.chunk.RandomBlockTickerChunk",
                    false, LevelChunk.class.getClassLoader());
            ticker.getMethod("leavesbegone$setRandomBlockTicks", LevelChunkTicks.class)
                    .invoke(this, new LevelChunkTicks<>());
        } catch (ReflectiveOperationException exception) {
            throw new IllegalStateException("PSA: incompatible Leaves Be Gone chunk ticker API", exception);
        }
    }
}
