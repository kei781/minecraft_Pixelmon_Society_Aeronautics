package dev.psa.qaconnect.v2;

import com.sun.tools.attach.VirtualMachine;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.Properties;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.Executor;

/** Local QA-only native connection request; never reads or alters authentication. */
public final class MinecraftQaConnect {
    public static void main(String[] args) throws Exception {
        if (args.length != 1 || !args[0].matches("[1-9][0-9]*"))
            throw new IllegalArgumentException("Usage: MinecraftQaConnect <owned QA Minecraft PID>");
        UUID run = UUID.randomUUID();
        String jar = Path.of(MinecraftQaConnect.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toString();
        var vm = VirtualMachine.attach(args[0]);
        try { vm.loadAgent(jar, run.toString()); } finally { vm.detach(); }
        System.out.println("PSA_QA_CONNECT queued run=" + run);
    }

    public static void agentmain(String options, Instrumentation instrumentation) throws Exception {
        UUID run = UUID.fromString(options);
        Path root = Path.of(System.getProperty("user.dir"));
        if (!Boolean.getBoolean("psa.modelAudit") || !Files.isRegularFile(root.resolve("psa-forge-client-profile.json")))
            throw new IllegalStateException("Owned opted-in PSA QA client required");
        Path setting = root.resolve(".psa-qa-connect.properties");
        if (Files.isSymbolicLink(setting)) throw new IllegalStateException("Real owner connection properties required");
        var properties = new Properties();
        try (var reader = Files.newBufferedReader(setting)) { properties.load(reader); }
        if (!properties.stringPropertyNames().equals(Set.of("owner", "server", "common_sha256"))
                || !"psa-owned-native-connection".equals(properties.getProperty("owner")))
            throw new IllegalStateException("Owner connection properties refused");
        String server = properties.getProperty("server"), common = properties.getProperty("common_sha256");
        if (!server.matches("[A-Za-z0-9][A-Za-z0-9.-]{0,252}:25573") || !common.matches("[a-f0-9]{64}"))
            throw new IllegalStateException("Explicit approved game target required");
        requireHash(root.resolve("mods/psa-aeronautics-experimental-forge-1.20.1.jar"), common);
        requireHash(root.resolve("mods/Pixelmon-1.20.1-9.2.3-universal.jar"),
            "8f2777f5a7cd2b5fc48ac3f5531d434af4120c7d40adc9929d5a3737c404246a");
        var classes = Arrays.stream(instrumentation.getAllLoadedClasses())
            .filter(type -> type.getName().equals("net.minecraft.client.Minecraft")).toList();
        if (classes.size() != 1) throw new IllegalStateException("Unique pinned Minecraft required");
        Class<?> minecraft = classes.get(0); Object client = minecraft.getMethod("m_91087_").invoke(null);
        Path directory = root.resolve("psa-qa-connect"); Files.createDirectories(directory);
        ((Executor) client).execute(() -> {
            try {
                if (field(client, "net.minecraft.client.multiplayer.ClientLevel") != null
                        || field(client, "net.minecraft.client.player.LocalPlayer") != null) {
                    write(directory, run, "active_world_refused", null); return;
                }
                ClassLoader loader = minecraft.getClassLoader();
                Class<?> screenType = loader.loadClass("net.minecraft.client.gui.screens.Screen");
                Object parent = field(client, screenType.getName());
                // A failed attempt leaves the native disconnected screen; a retry is safe
                // only there or at the title screen, never over gameplay or a prompt.
                if (!loader.loadClass("net.minecraft.client.gui.screens.TitleScreen").isInstance(parent)
                        && !loader.loadClass("net.minecraft.client.gui.screens.DisconnectedScreen").isInstance(parent)) {
                    write(directory, run, "connection_screen_required", null); return;
                }
                Class<?> addressType = loader.loadClass("net.minecraft.client.multiplayer.resolver.ServerAddress");
                Class<?> dataType = loader.loadClass("net.minecraft.client.multiplayer.ServerData");
                Class<?> connectType = loader.loadClass("net.minecraft.client.gui.screens.ConnectScreen");
                // Pinned 1.20.1 public API shapes, independent of named/SRG method spelling.
                Method parse = unique(addressType, addressType, String.class);
                Method connect = unique(connectType, void.class, screenType, minecraft, addressType, dataType, boolean.class);
                Object address = parse.invoke(null, server);
                Object data = dataType.getConstructor(String.class, String.class, boolean.class)
                    .newInstance("PSA paired QA", server, false);
                connect.invoke(null, parent, client, address, data, false);
                write(directory, run, "connect_requested", null); // require real server login separately
            } catch (Throwable failure) {
                Throwable cause = failure instanceof java.lang.reflect.InvocationTargetException ? failure.getCause() : failure;
                if (cause instanceof VirtualMachineError fatal) throw fatal;
                if (cause instanceof ThreadDeath fatal) throw fatal;
                write(directory, run, "failed", cause);
            }
        });
    }

    private static Object field(Object owner, String type) throws Exception {
        var fields = Arrays.stream(owner.getClass().getFields())
            .filter(value -> !Modifier.isStatic(value.getModifiers()) && value.getType().getName().equals(type)).toList();
        if (fields.size() != 1) throw new IllegalStateException("Unique native state field required");
        return fields.get(0).get(owner);
    }

    private static Method unique(Class<?> owner, Class<?> result, Class<?>... arguments) {
        var methods = Arrays.stream(owner.getMethods()).filter(value -> Modifier.isStatic(value.getModifiers())
            && value.getReturnType() == result && Arrays.equals(value.getParameterTypes(), arguments)).toList();
        if (methods.size() != 1) throw new IllegalStateException("Unique pinned native method required");
        return methods.get(0);
    }

    private static void requireHash(Path path, String expected) throws Exception {
        if (Files.isSymbolicLink(path)) throw new IllegalStateException("Real pinned mod required");
        var digest = MessageDigest.getInstance("SHA-256");
        try (var input = Files.newInputStream(path)) {
            byte[] buffer = new byte[65536]; int size;
            while ((size = input.read(buffer)) != -1) digest.update(buffer, 0, size);
        }
        if (!HexFormat.of().formatHex(digest.digest()).equals(expected))
            throw new IllegalStateException("Pinned QA mod differs");
    }

    private static void write(Path directory, UUID run, String result, Throwable failure) {
        String error = failure == null ? "" : failure.getClass().getName().replace("\\", "\\\\").replace("\"", "\\\"");
        String json = "{\"run\":\"" + run + "\",\"result\":\"" + result + "\",\"error_class\":\"" + error
            + "\",\"scope\":\"native QA connection request; no authentication/input/session modification\"}\n";
        try { Files.writeString(directory.resolve(run + ".json"), json, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE); }
        catch (java.io.IOException failureToWrite) { System.err.println("PSA_QA_CONNECT evidence write failed: " + failureToWrite.getClass().getName()); }
    }
}
