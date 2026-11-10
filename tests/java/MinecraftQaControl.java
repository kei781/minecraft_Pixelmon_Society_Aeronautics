package dev.psa.qacontrol;

import com.sun.tools.attach.VirtualMachine;
import java.io.IOException;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Method;
import java.lang.reflect.InvocationTargetException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.util.UUID;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

/** Local JDK attach helper for a deliberately opted-in, disposable Forge 1.20.1 client. */
public final class MinecraftQaControl {
    private static void validate(String action) {
        if (!action.equals("status") && !action.equals("reload") && !action.equals("stop"))
            throw new IllegalArgumentException("Allowed actions: status, reload, stop");
    }

    public static void main(String[] args) throws Exception {
        if (args.length != 2 || !args[0].matches("[1-9][0-9]*"))
            throw new IllegalArgumentException("Usage: MinecraftQaControl <owned Minecraft PID> <status|reload|stop>");
        validate(args[1]);
        var run = UUID.randomUUID();
        String jar = Path.of(MinecraftQaControl.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toString();
        var vm = VirtualMachine.attach(args[0]);
        try { vm.loadAgent(jar, args[1] + "," + run); }
        finally { vm.detach(); }
        System.out.println("PSA_QA_CONTROL queued action=" + args[1] + " run=" + run);
    }

    public static void agentmain(String options, Instrumentation instrumentation) throws Exception {
        String[] parts = options.split(",", -1);
        if (parts.length != 2) throw new IllegalArgumentException("Invalid control options");
        String action = parts[0]; validate(action); UUID run = UUID.fromString(parts[1]);
        Path root = Path.of(System.getProperty("user.dir"));
        if (!Boolean.getBoolean("psa.modelAudit") || !Files.isRegularFile(root.resolve("psa-forge-client-profile.json")))
            throw new IllegalStateException("Client is not an opted-in PSA QA instance");
        Class<?> minecraft = null;
        for (Class<?> type : instrumentation.getAllLoadedClasses()) {
            if (type.getName().equals("net.minecraft.client.Minecraft")) {
                if (minecraft != null) throw new IllegalStateException("Ambiguous Minecraft class");
                minecraft = type;
            }
        }
        if (minecraft == null) throw new IllegalStateException("Minecraft is not loaded");
        // Exact SRG names checked against the pinned Forge 1.20.1 mapping output.
        Object client = minecraft.getMethod("m_91087_").invoke(null);
        Method reload = minecraft.getMethod("m_91391_");
        Method stop = minecraft.getMethod("m_91395_");
        Path directory = root.resolve("psa-qa-control");
        Files.createDirectories(directory);
        ((Executor) client).execute(() -> {
            try {
                if (action.equals("reload")) {
                    var future = (CompletableFuture<?>) reload.invoke(client);
                    future.whenComplete((ignored, failure) ->
                            write(directory, run, action, failure == null ? "completed" : "failed", failure));
                } else if (action.equals("stop")) {
                    // This acknowledges the request only. Verify actual normal process exit separately.
                    stop.invoke(client);
                    write(directory, run, action, "stop_requested", null);
                } else write(directory, run, action, "completed", null);
            } catch (Throwable failure) {
                Throwable cause = failure instanceof InvocationTargetException ? failure.getCause() : failure;
                if (cause instanceof VirtualMachineError fatal) throw fatal;
                if (cause instanceof ThreadDeath fatal) throw fatal;
                write(directory, run, action, "failed", cause);
            }
        });
    }

    private static void write(Path directory, UUID run, String action, String result, Throwable failure) {
        String error = failure == null ? "" : failure.getClass().getName();
        String data = "{\"run\":\"" + run + "\",\"action\":\"" + action + "\",\"result\":\"" + result
                + "\",\"error_class\":\"" + error + "\",\"scope\":\"native Minecraft QA callback; no input simulation or authentication changes\"}\n";
        try {
            Files.writeString(directory.resolve(run + ".json"), data, StandardCharsets.UTF_8,
                    StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        } catch (IOException persistenceFailure) {
            System.err.println("PSA_QA_CONTROL FAILED run=" + run + " result=" + result + " error=" + persistenceFailure);
        }
    }
}
