package dev.psa.renderprobe.mixin;

import com.llamalad7.mixinextras.injector.wrapoperation.Operation;
import com.llamalad7.mixinextras.injector.wrapoperation.WrapOperation;
import com.simibubi.create.content.logistics.box.PackageEntity;
import com.simibubi.create.content.logistics.box.PackageVisual;
import dev.engine_room.flywheel.api.model.Model;
import dev.engine_room.flywheel.api.visual.DynamicVisual;
import dev.engine_room.flywheel.api.visualization.VisualizationContext;
import dev.engine_room.flywheel.lib.model.baked.PartialModel;
import dev.engine_room.flywheel.lib.visual.AbstractEntityVisual;
import dev.psa.renderprobe.RenderClient;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(value = PackageVisual.class, remap = false)
public abstract class PackageVisualProbeMixin extends AbstractEntityVisual<PackageEntity> {
    @Unique private PartialModel psa$partial;
    @Unique private boolean psa$nativeModelPresent;

    protected PackageVisualProbeMixin(VisualizationContext context, PackageEntity entity, float partialTick) {
        super(context, entity, partialTick);
    }

    @WrapOperation(method = "<init>", at = @At(value = "INVOKE", target =
            "Ldev/engine_room/flywheel/lib/model/Models;partial(Ldev/engine_room/flywheel/lib/model/baked/PartialModel;)Ldev/engine_room/flywheel/api/model/Model;"),
            remap = false, require = 1, expect = 1, allow = 1)
    private Model psa$nativePartial(PartialModel partial, Operation<Model> original) {
        Model model = original.call(partial);
        psa$partial = partial;
        psa$nativeModelPresent = model != null;
        return model;
    }

    @Inject(method = "beginFrame", at = @At("RETURN"), remap = false, require = 1, expect = 1, allow = 1)
    private void psa$frameReturned(DynamicVisual.Context context, CallbackInfo callback) {
        RenderClient.packageVisualFrame(entity, psa$partial == null ? null :
                ((PartialModelStateAccessor) (Object) psa$partial).psa$bakedModel(), psa$nativeModelPresent);
    }
}
