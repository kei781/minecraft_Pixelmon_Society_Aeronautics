package dev.psa.codecprobe;

import com.mojang.serialization.JsonOps;
import com.pixelmonmod.api.component.BetterTranslatableContents;
import com.pixelmonmod.api.component.TranslatedPlaceholder;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.ComponentSerialization;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.resources.RegistryOps;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.event.lifecycle.FMLLoadCompleteEvent;

/** Control profile: Pixelmon only, without CreativeCore or the compatibility patch. */
@Mod("psa_codec_probe")
public final class PixelmonCodecBaseline {
    public PixelmonCodecBaseline(IEventBus bus) { bus.addListener(this::loaded); }
    private void loaded(FMLLoadCompleteEvent event) {
        var ops = RegistryOps.create(JsonOps.INSTANCE, RegistryAccess.fromRegistryOfRegistries(BuiltInRegistries.REGISTRY));
        var input = MutableComponent.create(new BetterTranslatableContents(
            "psa.compat.test", "PSA test", new TranslatedPlaceholder[0]));
        var encoded = ComponentSerialization.CODEC.encodeStart(ops, input).getOrThrow();
        var decoded = ComponentSerialization.CODEC.parse(ops, encoded).getOrThrow();
        System.out.println("PSA_PIXELMON_BASELINE JSON: " + encoded);
        System.out.println("PSA_PIXELMON_BASELINE class: " + decoded.getContents().getClass().getName());
    }
}
