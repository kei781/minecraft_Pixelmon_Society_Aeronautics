package dev.psa.aliqa.v5;

import com.sun.tools.attach.VirtualMachine;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.InvocationTargetException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.security.MessageDigest;
import java.util.Arrays;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.Executor;

/** QA-only native factories and recipe observation; one labelled native tooltip control, no auth/input access. */
public final class AliClientQaControl {
    public static void main(String[] args) throws Exception {
        if (args.length != 1 || !args[0].matches("[1-9][0-9]*")) throw new IllegalArgumentException("Owned QA PID required");
        UUID run = UUID.randomUUID();
        String jar = Path.of(AliClientQaControl.class.getProtectionDomain().getCodeSource().getLocation().toURI()).toString();
        var vm = VirtualMachine.attach(args[0]);
        try { vm.loadAgent(jar, run.toString()); } finally { vm.detach(); }
        System.out.println("PSA_ALI_QA queued run=" + run);
    }

    public static void agentmain(String options, Instrumentation instrumentation) throws Exception {
        UUID run = UUID.fromString(options); Path root = Path.of(System.getProperty("user.dir"));
        if (!Boolean.getBoolean("psa.modelAudit") || !Files.isRegularFile(root.resolve("psa-forge-client-profile.json")))
            throw new IllegalStateException("Owned opted-in QA client required");
        requireHash(root.resolve("mods/AdvancedLootInfo-forge-1.20.1-1.12.0.jar"),
            "6a0b368a0c19476ce1c6e73ecd923855e5ef45834077dea1ae0ca94820ce8eb8");
        requireHash(root.resolve("mods/Pixelmon-1.20.1-9.2.3-universal.jar"),
            "8f2777f5a7cd2b5fc48ac3f5531d434af4120c7d40adc9929d5a3737c404246a");
        requireHash(root.resolve("mods/psa-aeronautics-experimental-forge-1.20.1.jar"),
            "351ecb0905a7f05a262a9401fe0e968402896f527e5983838ef2014641e3a3db");
        var classes = Arrays.stream(instrumentation.getAllLoadedClasses())
            .filter(type -> type.getName().equals("net.minecraft.client.Minecraft")).toList();
        if (classes.size() != 1) throw new IllegalStateException("Unique native Minecraft required");
        Class<?> minecraft = classes.get(0); Object client = minecraft.getMethod("m_91087_").invoke(null);
        Path directory = root.resolve("psa-ali-client-qa"); Files.createDirectories(directory);
        ((Executor) client).execute(() -> {
            var report = new LinkedHashMap<String, Object>(); report.put("run", run.toString());
            try {
                var screens = Arrays.stream(minecraft.getFields())
                    .filter(field -> field.getType().getName().equals("net.minecraft.client.gui.screens.Screen")).toList();
                if (screens.size() != 1) throw new IllegalStateException("Unique native screen field required");
                Object screen = screens.get(0).get(client);
                report.put("current_screen_class", screen == null ? "none" : screen.getClass().getName());
                boolean world = Arrays.stream(minecraft.getFields())
                    .filter(field -> field.getType().getName().equals("net.minecraft.client.multiplayer.ClientLevel"))
                    .anyMatch(field -> { try { return field.get(client) != null; } catch (IllegalAccessException e) { throw new IllegalStateException(e); } });
                report.put("native_client_world_present", world);
                if (!world) throw new IllegalStateException("Actual joined client world required");
                ClassLoader loader = minecraft.getClassLoader();
                Class<?> managerType = loader.loadClass("com.yanny.aci.manager.CorePluginManager");
                Object manager = managerType.getField("INSTANCE").get(null);
                Object serverRegistry = managerType.getField("serverRegistry").get(manager);
                Object clientRegistry = managerType.getField("clientRegistry").get(manager);
                report.put("server_registry_null", serverRegistry == null); report.put("client_registry_present", clientRegistry != null);
                if (clientRegistry == null) throw new IllegalStateException("Native client registry required");
                Object palette = clientRegistry.getClass().getMethod("getTooltipCache").invoke(clientRegistry);
                var nodesField = palette.getClass().getDeclaredField("idToNode"); nodesField.setAccessible(true);
                var nodes = (java.util.List<?>) nodesField.get(palette);
                if (nodes.size() > 500000) throw new IllegalStateException("Palette inspection bound exceeded");
                var before = java.util.List.copyOf(nodes);
                report.put("client_palette_size_before", before.size());
                Object first = palette.getClass().getMethod("getNodeById", int.class).invoke(palette, 0);
                report.put("existing_palette_node_zero_present", first != null);
                Class<?> nodeType = loader.loadClass("com.yanny.aci.tooltip.TooltipNode");
                var flagsField = nodeType.getDeclaredField("flags"); flagsField.setAccessible(true);
                int emptyFlagNodes = 0;
                for (Object node : before) if ((flagsField.getShort(node) & 8) != 0) emptyFlagNodes++;
                report.put("existing_native_empty_flag_nodes", emptyFlagNodes);
                try {
                    Object empty = nodeType.getMethod("empty").invoke(null);
                    report.put("empty_factory_success", true);
                    report.put("empty_in_basic_mode", nodeType.getMethod("isEmpty", boolean.class).invoke(empty, false));
                    report.put("empty_in_advanced_mode", nodeType.getMethod("isEmpty", boolean.class).invoke(empty, true));
                    report.put("empty_node_id_in_client_palette", palette.getClass().getMethod("getNodeId", nodeType).invoke(palette, empty));
                } catch (Throwable failure) {
                    Throwable cause = unwrap(failure); rethrowFatal(cause);
                    report.put("empty_factory_success", false); report.put("empty_factory_error_class", cause.getClass().getName());
                }
                report.put("existing_palette_node_zero_identity_preserved", first == palette.getClass().getMethod("getNodeById", int.class).invoke(palette, 0));
                boolean preserved = nodes.size() >= before.size();
                for (int index = 0; preserved && index < before.size(); index++) preserved = nodes.get(index) == before.get(index);
                report.put("client_palette_size_after", nodes.size());
                report.put("all_existing_palette_ids_identity_preserved", preserved);
                report.put("builder_control_scope", "One owned native key-only tooltip; may append one local cache entry, never changes existing IDs or sends a packet");
                try {
                    String controlKey = "PSA QA tooltip control";
                    Class<?> builderType = loader.loadClass("com.yanny.aci.tooltip.TooltipBuilder");
                    Object builder = builderType.getMethod("keyOnly", String.class).invoke(null, controlKey);
                    Object control = builderType.getMethod("build").invoke(builder);
                    report.put("native_builder_success", true);
                    report.put("native_builder_is_nonempty", !((Boolean) nodeType.getMethod("isEmpty", boolean.class).invoke(control, false)));
                    report.put("native_builder_has_key", nodeType.getMethod("hasKey").invoke(control));
                    var components = (java.util.List<?>) nodeType.getMethod("getComponents", int.class, boolean.class).invoke(control, 0, false);
                    Class<?> componentType = loader.loadClass("net.minecraft.network.chat.Component");
                    boolean renderedControl = false;
                    for (Object component : components)
                        if (((String) componentType.getMethod("getString").invoke(component)).contains(controlKey)) renderedControl = true;
                    report.put("native_builder_components_contain_control_key", renderedControl);
                    report.put("native_builder_id_in_client_palette", palette.getClass().getMethod("getNodeId", nodeType).invoke(palette, control));
                } catch (Throwable failure) {
                    Throwable cause = unwrap(failure); rethrowFatal(cause);
                    report.put("native_builder_success", false); report.put("native_builder_error_class", cause.getClass().getName());
                }
                boolean builderPreserved = nodes.size() >= before.size();
                for (int index = 0; builderPreserved && index < before.size(); index++) builderPreserved = nodes.get(index) == before.get(index);
                report.put("client_palette_size_after_owned_builder_control", nodes.size());
                report.put("all_existing_palette_ids_preserved_after_builder_control", builderPreserved);
                report.put("server_registry_identity_preserved", serverRegistry == managerType.getField("serverRegistry").get(manager));
                Class<?> emiApi = loader.loadClass("dev.emi.emi.api.EmiApi");
                Object recipes = emiApi.getMethod("getRecipeManager").invoke(null);
                Class<?> recipeManagerType = loader.loadClass("dev.emi.emi.api.recipe.EmiRecipeManager");
                var all = (java.util.List<?>) recipeManagerType.getMethod("getRecipes").invoke(recipes);
                if (all.size() > 250000) throw new IllegalStateException("Recipe inspection bound exceeded");
                report.put("total_emi_recipes", all.size());
                Class<?> recipeType = loader.loadClass("dev.emi.emi.api.recipe.EmiRecipe");
                Class<?> categoryType = loader.loadClass("dev.emi.emi.api.recipe.EmiRecipeCategory");
                var categories = new java.util.TreeMap<String, Integer>();
                for (Object recipe : all) if (recipe.getClass().getName().startsWith("com.yanny.ali.")) {
                    Object category = recipeType.getMethod("getCategory").invoke(recipe);
                    String id = categoryType.getMethod("getId").invoke(category).toString();
                    categories.merge(id, 1, Integer::sum);
                }
                report.put("ali_emi_recipes_by_category", categories);
                report.put("ali_emi_recipe_count", categories.values().stream().mapToInt(Integer::intValue).sum());
                var registeredCategories = (java.util.List<?>) recipeManagerType.getMethod("getCategories").invoke(recipes);
                if (registeredCategories.size() > 1024) throw new IllegalStateException("Category inspection bound exceeded");
                var perCategory = new java.util.TreeMap<String, Integer>();
                var recipeClasses = new java.util.TreeMap<String, Integer>();
                for (Object category : registeredCategories) {
                    String id = categoryType.getMethod("getId").invoke(category).toString();
                    if (!id.startsWith("ali:")) continue;
                    var entries = (java.util.List<?>) recipeManagerType.getMethod("getRecipes", categoryType).invoke(recipes, category);
                    if (entries.size() > 250000) throw new IllegalStateException("Category recipe bound exceeded");
                    perCategory.put(id, entries.size());
                    for (Object entry : entries) recipeClasses.merge(entry.getClass().getName(), 1, Integer::sum);
                }
                report.put("ali_emi_category_api_recipe_counts", perCategory);
                report.put("ali_emi_category_api_recipe_classes", recipeClasses);
                report.put("probe_completed", true);
            } catch (Throwable failure) {
                Throwable cause = unwrap(failure); rethrowFatal(cause);
                report.put("probe_completed", false); report.put("probe_error_class", cause.getClass().getName());
            }
            try {
                Class<?> gson = minecraft.getClassLoader().loadClass("com.google.gson.Gson");
                String json = (String) gson.getMethod("toJson", Object.class).invoke(gson.getConstructor().newInstance(), report);
                Files.writeString(directory.resolve(run + ".json"), json + "\n", StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
            } catch (Throwable failure) {
                Throwable cause = unwrap(failure); rethrowFatal(cause);
                System.err.println("PSA_ALI_QA evidence write failed: " + cause.getClass().getName());
            }
        });
    }

    private static Throwable unwrap(Throwable value) {
        while (value instanceof InvocationTargetException && value.getCause() != null) value = value.getCause();
        return value;
    }
    private static void rethrowFatal(Throwable value) {
        if (value instanceof VirtualMachineError fatal) throw fatal;
        if (value instanceof ThreadDeath fatal) throw fatal;
    }
    private static void requireHash(Path path, String expected) throws Exception {
        if (Files.isSymbolicLink(path)) throw new IllegalStateException("Real pinned input required");
        var hash = MessageDigest.getInstance("SHA-256");
        try (var input = Files.newInputStream(path)) {
            byte[] buffer = new byte[65536]; int count;
            while ((count = input.read(buffer)) != -1) hash.update(buffer, 0, count);
        }
        if (!HexFormat.of().formatHex(hash.digest()).equals(expected)) throw new IllegalStateException("Pinned input differs");
    }
}
