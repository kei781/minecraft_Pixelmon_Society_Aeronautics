package dev.psa.pixelmonfixture.mixin;

import com.pixelmonmod.pixelmon.api.pokemon.Pokemon;
import com.pixelmonmod.pixelmon.battles.controller.participants.WildPixelmonParticipant;
import dev.psa.pixelmonfixture.PixelmonFixture;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Redirect;

/** Constructor context only; original test bodies and assertions remain intact. */
@Mixin(targets = "com.pixelmonmod.pixelmon.api.test.notexamples.ClangorousSoulblazeCorrectBoostAmountTest", remap = false)
public abstract class ClangorousSoulblazeCorrectBoostAmountTestFixtureMixin {
    @Redirect(method = {"createKommoO", "createMagikarp"}, at = @At(value = "NEW", target =
        "([Lcom/pixelmonmod/pixelmon/api/pokemon/Pokemon;)Lcom/pixelmonmod/pixelmon/battles/controller/participants/WildPixelmonParticipant;"),
        remap = false, require = 2, expect = 2, allow = 2)
    private static WildPixelmonParticipant psa$worldParticipant(Pokemon[] pokemon) {
        return PixelmonFixture.participant(pokemon);
    }
}
