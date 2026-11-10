package dev.psa.aliresync;

import java.io.DataOutputStream;
import java.io.OutputStream;
import java.lang.reflect.Modifier;
import java.nio.charset.StandardCharsets;
import java.security.DigestOutputStream;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.IdentityHashMap;
import java.util.List;

/** Hashes native node semantics and ordered child IDs; never writes or emits tooltip contents. */
public final class AliPaletteFingerprint {
    public record Snapshot(int nodes, String sha256, int indexedKeyNodes) { }
    private AliPaletteFingerprint() { }

    public static Snapshot capture(Object palette, int prefix) {
        synchronized (palette) {
            try {
                var field = palette.getClass().getDeclaredField("idToNode"); field.setAccessible(true);
                var nodes = (List<?>) field.get(palette);
                int count = prefix < 0 ? nodes.size() : prefix;
                if (count < 0 || count > nodes.size() || count > 500000)
                    throw new IllegalStateException("Bounded native prefix required");
                var ids = new IdentityHashMap<Object, Integer>();
                for (int i = 0; i < count; i++) ids.put(nodes.get(i), i);
                var loader = palette.getClass().getClassLoader();
                Class<?> nodeType = loader.loadClass("com.yanny.aci.tooltip.TooltipNode");
                if (nodeType.getMethod("equals", Object.class).getDeclaringClass() != Object.class)
                    throw new IllegalStateException("Pinned native node identity semantics required");
                var fields = new java.util.HashMap<String, java.lang.reflect.Field>();
                for (String name : List.of("key", "values", "component", "flags", "children")) {
                    var value = nodeType.getDeclaredField(name); value.setAccessible(true); fields.put(name, value);
                }
                Class<?> component = loader.loadClass("net.minecraft.network.chat.Component");
                Class<?> serializer = loader.loadClass("net.minecraft.network.chat.Component$Serializer");
                // Pinned 1.20.1 SRG toJson(Component). There is also toStableJson with the same API shape.
                var componentSerializer = serializer.getMethod("m_130703_", component);
                if (!Modifier.isStatic(componentSerializer.getModifiers()) || componentSerializer.getReturnType() != String.class)
                    throw new IllegalStateException("Pinned native component serializer required");
                var hash = MessageDigest.getInstance("SHA-256");
                int indexedKeys = 0;
                try (var output = new DataOutputStream(new DigestOutputStream(OutputStream.nullOutputStream(), hash))) {
                    text(output, "psa-native-tooltip-ordered-semantics-v2"); output.writeInt(count);
                    for (int i = 0; i < count; i++) {
                        Object node = nodes.get(i); output.writeInt(i);
                        short flags = fields.get("flags").getShort(node);
                        // Native encode sets 0x100 only in its wire-local flags when it sends a
                        // translation-table index. decode keeps this bit after resolving the key.
                        // Hash the resolved key below and every semantic flag; exclude only that
                        // transport representation bit, recording its count separately.
                        if ((flags & 0x100) != 0) indexedKeys++;
                        output.writeShort(flags & ~0x100);
                        text(output, (String) fields.get("key").get(node));
                        var values = (String[]) fields.get("values").get(node);
                        output.writeInt(values == null ? -1 : values.length);
                        if (values != null) for (String value : values) text(output, value);
                        Object value = fields.get("component").get(node);
                        text(output, value == null ? null : (String) componentSerializer.invoke(null, value));
                        var children = (List<?>) fields.get("children").get(node);
                        output.writeInt(children.size());
                        for (Object child : children) {
                            Integer id = ids.get(child);
                            if (id == null) throw new IllegalStateException("Child outside indexed native prefix");
                            output.writeInt(id);
                        }
                    }
                }
                return new Snapshot(count, HexFormat.of().formatHex(hash.digest()), indexedKeys);
            } catch (ReflectiveOperationException | java.io.IOException | java.security.NoSuchAlgorithmException failure) {
                throw new IllegalStateException("Native palette fingerprint failed", failure);
            }
        }
    }

    private static void text(DataOutputStream output, String value) throws java.io.IOException {
        if (value == null) { output.writeInt(-1); return; }
        byte[] data = value.getBytes(StandardCharsets.UTF_8);
        if (data.length > 1000000) throw new IllegalStateException("Tooltip scalar bound exceeded");
        output.writeInt(data.length); output.write(data);
    }
}
