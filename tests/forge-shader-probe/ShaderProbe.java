package dev.psa.shaderprobe;

import com.mojang.serialization.Codec;
import io.netty.buffer.Unpooled;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.network.syncher.EntityDataSerializer;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.event.server.ServerStartedEvent;
import net.minecraftforge.fml.common.Mod;

import java.awt.Color;
import java.lang.reflect.Constructor;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

/** Test-only: exercise real Pixelmon serializers in a real dedicated Forge JVM. */
@Mod("psashaderprobe")
public final class ShaderProbe {
    public ShaderProbe() {
        MinecraftForge.EVENT_BUS.addListener(this::started);
    }

    private void started(ServerStartedEvent event) {
        try {
            run(Boolean.getBoolean("psa.shader.baseline"));
        } catch (Throwable failure) {
            System.err.println("PSA_SHADER_PROBE FAILED");
            failure.printStackTrace();
        } finally {
            event.getServer().halt(false);
        }
    }

    @SuppressWarnings("unchecked")
    private static void run(boolean baseline) throws Exception {
        Class<?> registry = Class.forName("com.pixelmonmod.pixelmon.client.render.shader.PixelmonCodecs");
        Map<String, Codec<?>> codecs = (Map<String, Codec<?>>) registry.getField("CODECS").get(null);
        Class<?> shader = Class.forName("com.pixelmonmod.pixelmon.client.render.shader.ShaderParameters");
        Class<?> value = Class.forName("com.pixelmonmod.pixelmon.client.render.shader.ShaderParameters$Value");
        Constructor<?> valueConstructor = value.getConstructor(Codec.class, Object.class);
        Constructor<?> shaderConstructor = shader.getConstructor(ResourceLocation.class, Map.class,
                Color.class, boolean.class, boolean.class, boolean.class, boolean.class);
        EntityDataSerializer<Object> serializer = (EntityDataSerializer<Object>) shader.getField("SHADER_DATA_SERIALIZER").get(null);
        EntityDataSerializer<Optional<Object>> optional = (EntityDataSerializer<Optional<Object>>) shader.getField("OPTIONAL_SHADER_DATA_SERIALIZER").get(null);
        Map<String, Object> parameters = new LinkedHashMap<>();
        parameters.put("integer", valueConstructor.newInstance(Codec.INT, 42));
        parameters.put("float", valueConstructor.newInstance(Codec.FLOAT, 0.35F));
        parameters.put("array", valueConstructor.newInstance(Codec.FLOAT.listOf(), List.of(1.0F, 0.5F, 0.0F, 0.1F)));
        Object sample = shaderConstructor.newInstance(new ResourceLocation("pixelmon", "rendertype_entity_smooth_cutout_fresnel"),
                parameters, new Color(12, 34, 56, 78), true, false, true, false);
        if (baseline) {
            require(codecs.isEmpty(), "Unexpected pre-initialized baseline registry");
            FriendlyByteBuf buffer = new FriendlyByteBuf(Unpooled.buffer());
            try {
                try { serializer.write(buffer, sample); throw new AssertionError("Expected missing-codec NPE"); }
                catch (NullPointerException expected) { System.out.println("PSA_SHADER_PROBE baseline_missing_codec_npe=true"); }
            } finally { buffer.release(); }
            registry.getMethod("init").invoke(null);
            require(codecs.keySet().equals(Set.of("int", "float", "float_array")), "Unexpected default wire registry");
            buffer = new FriendlyByteBuf(Unpooled.buffer());
            try {
                serializer.write(buffer, sample);
                try { serializer.read(buffer); throw new AssertionError("Expected invalid color range"); }
                catch (IllegalArgumentException expected) {
                    require(expected.getMessage().contains("Color parameter outside"), "Unexpected baseline read failure");
                    System.out.println("PSA_SHADER_PROBE baseline_color_range_failure=true");
                }
            } finally { buffer.release(); }
            System.out.println("PSA_SHADER_PROBE BASELINE_REPRODUCED");
            return;
        }
        require(codecs.keySet().equals(Set.of("int", "float", "float_array")), "Incomplete patched wire registry");
        // The upstream init method remains safe to call again, including list codec equality.
        registry.getMethod("init").invoke(null);
        for (Color color : List.of(Color.WHITE, Color.BLACK, new Color(12, 34, 56, 78), new Color(255, 0, 128, 0))) {
            Object original = shaderConstructor.newInstance(new ResourceLocation("pixelmon", "rendertype_entity_smooth_cutout_fresnel"),
                    parameters, color, true, false, true, false);
            FriendlyByteBuf buffer = new FriendlyByteBuf(Unpooled.buffer());
            try {
                serializer.write(buffer, original);
                sameShader(original, serializer.read(buffer));
                require(buffer.readableBytes() == 0, "Unread shader packet bytes");
            } finally { buffer.release(); }
        }
        for (Optional<Object> original : List.<Optional<Object>>of(Optional.empty(), Optional.of(sample))) {
            FriendlyByteBuf buffer = new FriendlyByteBuf(Unpooled.buffer());
            try {
                optional.write(buffer, original);
                Optional<Object> decoded = optional.read(buffer);
                require(original.isPresent() == decoded.isPresent(), "Optional shader presence changed");
                if (original.isPresent()) sameShader(original.get(), decoded.orElseThrow());
                require(buffer.readableBytes() == 0, "Unread optional shader bytes");
            } finally { buffer.release(); }
        }
        Map<String, Object> unsupported = Map.of("unknown", valueConstructor.newInstance(Codec.STRING, "unsupported"));
        Object bad = shaderConstructor.newInstance(new ResourceLocation("pixelmon", "unsupported_test"), unsupported, Color.WHITE,
                false, false, false, false);
        FriendlyByteBuf buffer = new FriendlyByteBuf(Unpooled.buffer());
        try {
            try { serializer.write(buffer, bad); throw new AssertionError("Unsupported codec silently accepted"); }
            catch (NullPointerException expected) { System.out.println("PSA_SHADER_PROBE unsupported_codec_rejected=true"); }
        } finally { buffer.release(); }
        System.out.println("PSA_SHADER_PROBE PATCHED_PASS cases=7 codecs=int,float,float_array");
    }

    private static void sameShader(Object original, Object decoded) throws Exception {
        for (String name : List.of("id", "renderColor", "onlyShader", "withTexture", "wireframe", "vertex"))
            require(field(original, name).equals(field(decoded, name)), "Shader field differs: " + name);
        Map<?, ?> left = (Map<?, ?>) field(original, "parameters");
        Map<?, ?> right = (Map<?, ?>) field(decoded, "parameters");
        require(left.keySet().equals(right.keySet()), "Shader parameter keys differ");
        for (Object name : left.keySet()) {
            require(field(left.get(name), "codec").equals(field(right.get(name), "codec")), "Shader codec differs");
            require(field(left.get(name), "value").equals(field(right.get(name), "value")), "Shader value differs");
        }
    }

    private static Object field(Object instance, String name) throws Exception {
        var field = instance.getClass().getDeclaredField(name);
        field.setAccessible(true);
        return field.get(instance);
    }

    private static void require(boolean condition, String message) {
        if (!condition) throw new AssertionError(message);
    }
}
