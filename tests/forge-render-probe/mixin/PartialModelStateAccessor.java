package dev.psa.renderprobe.mixin;

import dev.engine_room.flywheel.lib.model.baked.PartialModel;
import net.minecraft.client.resources.model.BakedModel;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.gen.Accessor;

/** Read native state; never resolve or replace a model for the game. */
@Mixin(value = PartialModel.class, remap = false)
public interface PartialModelStateAccessor {
    @Accessor(value = "bakedModel", remap = false)
    BakedModel psa$bakedModel();
}
