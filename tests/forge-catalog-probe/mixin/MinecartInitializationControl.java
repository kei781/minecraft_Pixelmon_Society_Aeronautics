package dev.psa.catalogprobe.mixin;

import net.minecraft.world.entity.vehicle.AbstractMinecart;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** Test-only: exercise both orders of the sibling cart classes found by the audit. */
@Mixin(AbstractMinecart.class)
public abstract class MinecartInitializationControl {
    @Inject(method = "<clinit>", at = @At("RETURN"), require = 1)
    private static void psa$controlMinecartInitialization(CallbackInfo ci) throws ClassNotFoundException {
        String order = System.getProperty("psa.catalog.cartOrder", "natural");
        if (order.equals("natural")) return;
        String first = switch (order) {
            case "tank-first" -> "com.alc.moreminecarts.entities.TankCartEntity";
            case "flag-first" -> "com.alc.moreminecarts.entities.FlagCartEntity";
            default -> throw new IllegalArgumentException("Unknown QA cart order: " + order);
        };
        Class.forName(first);
        System.out.println("PSA_CART_ORDER requested=" + order);
    }
}
