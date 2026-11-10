package dev.psa.aliresyncqa.v2;

import com.sun.tools.attach.VirtualMachine;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Modifier;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.Arrays;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.Executor;

/** Closed native QA actions on the explicitly marked local resync instance. No arbitrary targets or auth access. */
public final class AliResyncQaControl {
    private static final Set<String> ACTIONS = Set.of("connect_qa", "before_reload", "after_reload", "final", "request_native_reload", "arm_render_reload", "arm_disconnect_reload", "disconnected_status");
    public static void main(String[] args) throws Exception {
        if (args.length != 2 || !args[0].matches("[1-9][0-9]*") || !ACTIONS.contains(args[1]))
            throw new IllegalArgumentException("Owned PID and closed resync action required");
        UUID run = UUID.randomUUID();
        String jar = Path.of(AliResyncQaControl.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toString();
        var vm = VirtualMachine.attach(args[0]);
        try { vm.loadAgent(jar, run + "," + args[1]); } finally { vm.detach(); }
        System.out.println("PSA_ALI_RESYNC queued run=" + run);
    }
    public static void agentmain(String options, Instrumentation instrumentation) throws Exception {
        String[] pieces = options.split(",", -1);
        if (pieces.length != 2 || !ACTIONS.contains(pieces[1])) throw new IllegalArgumentException("Closed resync action required");
        UUID run = UUID.fromString(pieces[0]); String action = pieces[1];
        Path root = Path.of(System.getProperty("user.dir")), marker = root.resolve(".psa-ali-resync-trace");
        if (!Boolean.getBoolean("psa.modelAudit") || Files.isSymbolicLink(marker)
                || !Files.readString(marker).equals("psa-owned-ali-resync-v1\n")
                || !Files.isRegularFile(root.resolve("psa-forge-client-profile.json")))
            throw new IllegalStateException("Owned opted-in resync client required");
        var types = Arrays.stream(instrumentation.getAllLoadedClasses())
            .filter(type -> type.getName().equals("net.minecraft.client.Minecraft")).toList();
        if (types.size() != 1) throw new IllegalStateException("Unique native Minecraft required");
        Class<?> minecraft = types.get(0); Object client = minecraft.getMethod("m_91087_").invoke(null);
        Path directory = root.resolve("psa-ali-resync-control"); Files.createDirectories(directory);
        ((Executor) client).execute(() -> {
            try {
                var loader = minecraft.getClassLoader();
                if (action.equals("connect_qa")) {
                    if (field(client, "net.minecraft.client.multiplayer.ClientLevel") != null
                            || field(client, "net.minecraft.client.player.LocalPlayer") != null)
                        throw new IllegalStateException("Refuse active world replacement");
                    Class<?> screenType = loader.loadClass("net.minecraft.client.gui.screens.Screen");
                    Object parent = field(client, screenType.getName());
                    if (!loader.loadClass("net.minecraft.client.gui.screens.TitleScreen").isInstance(parent)
                            && !loader.loadClass("net.minecraft.client.gui.screens.DisconnectedScreen").isInstance(parent))
                        throw new IllegalStateException("Native title/disconnected screen required");
                    Class<?> addressType = loader.loadClass("net.minecraft.client.multiplayer.resolver.ServerAddress");
                    Class<?> dataType = loader.loadClass("net.minecraft.client.multiplayer.ServerData");
                    Class<?> connectType = loader.loadClass("net.minecraft.client.gui.screens.ConnectScreen");
                    String target = "127.0.0.1:25574";
                    var parse = unique(addressType, addressType, String.class);
                    var connect = unique(connectType, void.class, screenType, minecraft, addressType, dataType, boolean.class);
                    Object address = parse.invoke(null, target);
                    Object data = dataType.getConstructor(String.class, String.class, boolean.class).newInstance("PSA owned resync QA", target, false);
                    connect.invoke(null, parent, client, address, data, false);
                    write(directory, run, action, "connect_requested", "");
                    return;
                }
                if (action.equals("disconnected_status")) {
                    if (field(client, "net.minecraft.client.multiplayer.ClientLevel") != null
                            || field(client, "net.minecraft.client.player.LocalPlayer") != null)
                        throw new IllegalStateException("Native disconnection not completed");
                    write(directory, run, action, "native_world_and_player_absent", ""); return;
                }
                if (field(client, "net.minecraft.client.multiplayer.ClientLevel") == null
                        || field(client, "net.minecraft.client.player.LocalPlayer") == null)
                    throw new IllegalStateException("Actual joined QA world required");
                if (action.equals("request_native_reload") || action.startsWith("arm_")) {
                    if (action.startsWith("arm_")) {
                        Class<?> dataType = loader.loadClass("net.minecraft.client.multiplayer.ServerData");
                        var getters = Arrays.stream(minecraft.getMethods()).filter(method -> !Modifier.isStatic(method.getModifiers())
                            && method.getReturnType() == dataType && method.getParameterCount() == 0).toList();
                        if (getters.size() != 1) throw new IllegalStateException("Unique current server API required");
                        Object current = getters.get(0).invoke(client); boolean ownedTarget = false;
                        if (current != null) for (var value : dataType.getFields())
                            if (value.getType() == String.class && !Modifier.isStatic(value.getModifiers())
                                    && "127.0.0.1:25574".equals(value.get(current))) ownedTarget = true;
                        if (!ownedTarget) throw new IllegalStateException("Fixed loopback QA endpoint required");
                        loader.loadClass("dev.psa.aliresync.TraceState").getMethod("armStress", String.class)
                            .invoke(null, action.equals("arm_render_reload") ? "render" : "disconnect");
                    }
                    Class<?> managerType = loader.loadClass("com.yanny.aci.manager.CorePluginManager");
                    Object manager = managerType.getField("INSTANCE").get(null);
                    Object registry = managerType.getField("clientRegistry").get(manager);
                    if (registry == null) throw new IllegalStateException("Native client registry required");
                    registry.getClass().getMethod("reloadLootData").invoke(registry);
                    loader.loadClass("dev.emi.emi.runtime.EmiReloadManager").getMethod("reload").invoke(null);
                    write(directory, run, action, "reload_requested", "");
                } else {
                    loader.loadClass("dev.psa.aliresync.TraceState").getMethod("captureClient", String.class).invoke(null, action);
                    write(directory, run, action, "completed", "");
                }
            } catch (Throwable failure) {
                while (failure instanceof java.lang.reflect.InvocationTargetException && failure.getCause() != null) failure = failure.getCause();
                if (failure instanceof VirtualMachineError fatal) throw fatal;
                if (failure instanceof ThreadDeath fatal) throw fatal;
                write(directory, run, action, "failed", failure.getClass().getName());
            }
        });
    }
    private static Object field(Object owner, String type) throws Exception {
        var fields = Arrays.stream(owner.getClass().getFields())
            .filter(field -> !Modifier.isStatic(field.getModifiers()) && field.getType().getName().equals(type)).toList();
        if (fields.size() != 1) throw new IllegalStateException("Unique native state field required");
        return fields.get(0).get(owner);
    }
    private static java.lang.reflect.Method unique(Class<?> owner, Class<?> result, Class<?>... args) {
        var methods = Arrays.stream(owner.getMethods()).filter(method -> Modifier.isStatic(method.getModifiers())
            && method.getReturnType() == result && Arrays.equals(method.getParameterTypes(), args)).toList();
        if (methods.size() != 1) throw new IllegalStateException("Unique pinned native API required");
        return methods.get(0);
    }
    private static void write(Path directory, UUID run, String action, String result, String error) {
        String json = "{\"run\":\"" + run + "\",\"action\":\"" + action + "\",\"result\":\"" + result + "\",\"error_class\":\"" + error + "\"}\n";
        try { Files.writeString(directory.resolve(run + ".json"), json, StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE); }
        catch (java.io.IOException failure) { throw new IllegalStateException("Native resync control evidence write failed", failure); }
    }
}
