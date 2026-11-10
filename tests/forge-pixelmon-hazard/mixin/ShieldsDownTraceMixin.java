package dev.psa.hazardtrace.mixin;

import com.pixelmonmod.pixelmon.api.test.TestResult;
import com.pixelmonmod.pixelmon.battles.attacks.Attack;
import com.pixelmonmod.pixelmon.battles.controller.BattleController;
import com.pixelmonmod.pixelmon.battles.controller.participants.WildPixelmonParticipant;
import dev.psa.hazardtrace.HazardTrace;
import java.util.concurrent.CompletionStage;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Passive checkpoints plus separately opted-in post-assert probes; no return replacement. */
@Mixin(targets = "com.pixelmonmod.pixelmon.api.test.notexamples.ShieldsDownRemovesHazardsTest", remap = false)
public abstract class ShieldsDownTraceMixin {
    @Inject(method = "createMinior", at = @At("RETURN"), require = 1, expect = 1, allow = 1, remap = false)
    private static void psa$capture(CallbackInfoReturnable<WildPixelmonParticipant> result) { HazardTrace.capture(result.getReturnValue()); }

    @Inject(method = "lambda$testShieldsDownRemovesHazards$2", at = @At("HEAD"), require = 1, expect = 1, allow = 1, remap = false)
    private static void psa$attacks(WildPixelmonParticipant first, Attack spikes, WildPixelmonParticipant second,
            WildPixelmonParticipant third, Attack rock, WildPixelmonParticipant fourth, BattleController battle,
            CallbackInfoReturnable<CompletionStage<?>> result) { HazardTrace.attacks(first); }

    @Inject(method = "lambda$testShieldsDownRemovesHazards$0", at = @At("HEAD"), require = 1, expect = 1, allow = 1, remap = false)
    private static void psa$beforeEnd(CallbackInfo callback) { HazardTrace.snapshot("before_end_turn"); }

    @Inject(method = "lambda$testShieldsDownRemovesHazards$0", at = @At("RETURN"), require = 1, expect = 1, allow = 1, remap = false)
    private static void psa$afterEnd(CallbackInfo callback) { HazardTrace.snapshot("after_end_turn"); }

    @Inject(method = "lambda$testShieldsDownRemovesHazards$3", at = @At("RETURN"), require = 4, expect = 4, allow = 4, remap = false)
    private static void psa$result(CallbackInfoReturnable<TestResult> result) { HazardTrace.finish(result.getReturnValue()); }
}
