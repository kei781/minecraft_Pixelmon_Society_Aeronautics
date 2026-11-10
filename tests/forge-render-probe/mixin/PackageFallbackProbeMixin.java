package dev.psa.renderprobe.mixin;

import com.mojang.blaze3d.vertex.PoseStack;
import com.simibubi.create.content.logistics.box.PackageRenderer;
import dev.engine_room.flywheel.lib.model.baked.PartialModel;
import dev.psa.renderprobe.RenderClient;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.world.entity.Entity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(value = PackageRenderer.class,
        targets = "ru.zznty.create_factory_logistics.logistics.jar.JarPackageRenderer", remap = false)
public abstract class PackageFallbackProbeMixin {
    @Inject(method = "renderBox(Lnet/minecraft/world/entity/Entity;FLcom/mojang/blaze3d/vertex/PoseStack;Lnet/minecraft/client/renderer/MultiBufferSource;ILdev/engine_room/flywheel/lib/model/baked/PartialModel;)V",
            at = @At(value = "INVOKE", target =
            "Lnet/createmod/catnip/render/CachedBuffers;partial(Ldev/engine_room/flywheel/lib/model/baked/PartialModel;Lnet/minecraft/world/level/block/state/BlockState;)Lnet/createmod/catnip/render/SuperByteBuffer;",
            shift = At.Shift.AFTER), remap = false, require = 1, expect = 1, allow = 1)
    private static void psa$cachedPartial(Entity entity, float yaw, PoseStack pose, MultiBufferSource buffers,
            int light, PartialModel partial, CallbackInfo callback) {
        RenderClient.packageFallback(entity, ((PartialModelStateAccessor) (Object) partial).psa$bakedModel());
    }
}
