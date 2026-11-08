package dev.psa.codecprobe;

import java.lang.reflect.Method;
import com.google.gson.JsonElement;
import com.mojang.serialization.JsonOps;
import com.pixelmonmod.api.component.BetterTranslatableContents;
import com.pixelmonmod.api.component.TranslatedPlaceholder;
import net.minecraft.core.RegistryAccess;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.ComponentContents;
import net.minecraft.network.chat.ComponentSerialization;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.network.chat.contents.PlainTextContents;
import net.minecraft.network.chat.contents.TranslatableContents;
import net.minecraft.resources.RegistryOps;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;
import net.neoforged.bus.api.IEventBus;
import net.neoforged.fml.common.Mod;
import net.neoforged.fml.event.lifecycle.FMLLoadCompleteEvent;
import team.creative.creativecore.common.util.text.content.ContentItemStack;

/** Test-only mod: runs codec assertions in the real NeoForge/Pixelmon environment. */
@Mod("psa_codec_probe")
public final class CodecProbe {
    public CodecProbe(IEventBus bus) {
        bus.addListener(this::loaded);
    }

    private void loaded(FMLLoadCompleteEvent event) {
        try {
            Method hook = null;
            for (Method method : ComponentSerialization.class.getDeclaredMethods()) {
                if (method.getName().contains("psa$addItemStackType")) {
                    if (hook != null) throw new AssertionError("Duplicate compatibility hook");
                    hook = method;
                }
            }
            if (hook == null) throw new AssertionError("Compatibility hook was not applied");
            hook.setAccessible(true);
            ComponentContents.Type<?>[] initial = { PlainTextContents.TYPE, BetterTranslatableContents.TYPE };
            ComponentContents.Type<?>[] extended = (ComponentContents.Type<?>[]) hook.invoke(null, (Object) initial);
            if (extended.getClass() != initial.getClass() || extended.length != 3
                || extended[0] != initial[0] || extended[1] != initial[1]
                || extended[2] != ContentItemStack.TYPE) {
                throw new AssertionError("Compatibility hook must preserve both original types and append the item-stack type");
            }
            if (hook.invoke(null, (Object) extended) != extended) {
                throw new AssertionError("Compatibility hook must not append a duplicate type");
            }
            var access = RegistryAccess.fromRegistryOfRegistries(BuiltInRegistries.REGISTRY);
            var ops = RegistryOps.create(JsonOps.INSTANCE, access);
            Component creative = MutableComponent.create(new ContentItemStack(new ItemStack(Items.STONE)))
                .append(Component.literal(" tail"));
            JsonElement creativeJson = ComponentSerialization.CODEC.encodeStart(ops, creative).getOrThrow();
            Component decodedCreative = ComponentSerialization.CODEC.parse(ops, creativeJson).getOrThrow();
            if (!(decodedCreative.getContents() instanceof ContentItemStack content)
                || !content.stack().is(Items.STONE) || decodedCreative.getSiblings().size() != 1) {
                throw new AssertionError("CreativeCore item-stack component roundtrip failed");
            }
            Component pixelmon = MutableComponent.create(new BetterTranslatableContents(
                "psa.compat.test", "PSA test", new TranslatedPlaceholder[0]));
            JsonElement pixelmonJson = ComponentSerialization.CODEC.encodeStart(ops, pixelmon).getOrThrow();
            Component decodedPixelmon = ComponentSerialization.CODEC.parse(ops, pixelmonJson).getOrThrow();
            // Pixelmon-only control profile also decodes the untyped, empty-args
            // form as vanilla TranslatableContents. Preserve that baseline.
            if (decodedPixelmon.getContents().getClass() != TranslatableContents.class
                || !(decodedPixelmon.getContents() instanceof TranslatableContents translated)
                || !translated.getKey().equals("psa.compat.test") || !"PSA test".equals(translated.getFallback())) {
                throw new AssertionError("Pixelmon legacy translation differs from the Pixelmon-only control");
            }
            var typedPixelmonJson = pixelmonJson.getAsJsonObject().deepCopy();
            typedPixelmonJson.addProperty("type", BetterTranslatableContents.TYPE.getSerializedName());
            Component decodedTyped = ComponentSerialization.CODEC.parse(ops, typedPixelmonJson).getOrThrow();
            if (!(decodedTyped.getContents() instanceof BetterTranslatableContents typed)
                || !typed.getKey().equals("psa.compat.test")) {
                throw new AssertionError("Explicit Pixelmon component type was not preserved");
            }
            System.out.println("PSA_CODEC_PROBE PASS: component append, idempotence, CreativeCore roundtrip, Pixelmon legacy baseline and explicit type");
            System.out.println("PSA_CODEC_PROBE CreativeCore JSON: " + creativeJson);
            System.out.println("PSA_CODEC_PROBE Pixelmon JSON: " + pixelmonJson);
        } catch (Exception error) {
            throw new IllegalStateException("PSA_CODEC_PROBE failed", error);
        }
    }
}
