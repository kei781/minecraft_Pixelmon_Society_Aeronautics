package dev.psa.catalogprobe;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Comparator;
import net.minecraft.network.syncher.EntityDataAccessor;
import net.minecraft.network.syncher.EntityDataSerializers;
import net.minecraft.nbt.CompoundTag;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.item.ItemStack;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.common.util.FakePlayerFactory;
import net.minecraftforge.event.server.ServerStartedEvent;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.loading.FMLPaths;
import net.minecraftforge.registries.ForgeRegistries;

/** Test-only enumeration/serialization and player schema; not a gameplay pass. */
@Mod("psacatalogprobe")
public final class CatalogProbe {
    public CatalogProbe() {
        MinecraftForge.EVENT_BUS.addListener(this::started);
    }

    public static void write(String filename, JsonObject value) throws Exception {
        Path directory = FMLPaths.GAMEDIR.get().resolve("psa-validation");
        Files.createDirectories(directory);
        Files.writeString(directory.resolve(filename), new GsonBuilder().setPrettyPrinting().create().toJson(value) + "\n");
    }

    public static JsonObject playerSchema(Player player) throws Exception {
        String[][] targets = {
            {"tschipp.carryon.common.carry.CarryOnDataManager", "CARRY_DATA_KEY"},
            {"com.pixelmonmod.pixelmon.listener.EntityPlayerExtension", "dwPokeballs"},
            {"com.pixelmonmod.pixelmon.listener.EntityPlayerExtension", "dwMegaItem"},
            {"com.pixelmonmod.pixelmon.listener.EntityPlayerExtension", "dwMegaItemsUnlocked"},
            {"com.pixelmonmod.pixelmon.listener.EntityPlayerExtension", "dwShinyCharm"},
            {"com.pixelmonmod.pixelmon.listener.EntityPlayerExtension", "dwOvalCharm"},
            {"com.pixelmonmod.pixelmon.listener.EntityPlayerExtension", "dwExpCharm"},
            {"com.pixelmonmod.pixelmon.listener.EntityPlayerExtension", "dwCatchingCharm"},
            {"com.pixelmonmod.pixelmon.listener.EntityPlayerExtension", "dwMarkCharm"},
            {"com.pixelmonmod.pixelmon.listener.EntityPlayerExtension", "dwHween"}
        };
        return schema(player, targets);
    }

    @SuppressWarnings({"rawtypes", "unchecked"})
    public static JsonObject schema(Entity player, String[][] targets) throws Exception {
        JsonObject result = new JsonObject();
        result.addProperty("entity_class", player.getClass().getName());
        JsonArray fields = new JsonArray();
        java.util.HashSet<Integer> ids = new java.util.HashSet<>();
        for (String[] target : targets) {
            var reflected = Class.forName(target[0]).getDeclaredField(target[1]);
            reflected.setAccessible(true);
            EntityDataAccessor accessor = (EntityDataAccessor) reflected.get(null);
            if (!ids.add(accessor.getId())) throw new IllegalStateException("Duplicate entity data ID: " + accessor.getId());
            Object value = player.getEntityData().get(accessor);
            JsonObject field = new JsonObject();
            field.addProperty("owner", target[0]);
            field.addProperty("field", target[1]);
            field.addProperty("id", accessor.getId());
            field.addProperty("serializer", accessor.getSerializer() == EntityDataSerializers.STRING ? "string"
                    : accessor.getSerializer() == EntityDataSerializers.COMPOUND_TAG ? "compound"
                    : accessor.getSerializer() == EntityDataSerializers.BYTE ? "byte" : "other");
            field.addProperty("actual_value_class", value == null ? "null" : value.getClass().getName());
            fields.add(field);
        }
        result.add("fields", fields);
        return result;
    }

    private void started(ServerStartedEvent event) {
        try {
            JsonObject report = new JsonObject();
            report.addProperty("scope", "registered modded IDs and default stack roundtrip only");
            report.addProperty("world_summoning_or_client_render_verified", false);
            JsonArray items = new JsonArray();
            int passed = 0;
            int failed = 0;
            for (ResourceLocation id : ForgeRegistries.ITEMS.getKeys().stream().sorted(Comparator.comparing(ResourceLocation::toString)).toList()) {
                if (id.getNamespace().equals("minecraft")) continue;
                JsonObject row = new JsonObject();
                row.addProperty("id", id.toString());
                try {
                    ItemStack original = ForgeRegistries.ITEMS.getValue(id).getDefaultInstance();
                    if (original.isEmpty()) throw new IllegalStateException("Empty default stack");
                    CompoundTag tag = original.save(new CompoundTag());
                    ItemStack decoded = ItemStack.of(tag);
                    if (!ItemStack.isSameItemSameTags(original, decoded) || original.getCount() != decoded.getCount())
                        throw new IllegalStateException("Default stack roundtrip differs");
                    row.addProperty("default_stack_snbt", tag.toString());
                    row.addProperty("passed", true);
                    passed++;
                } catch (Throwable failure) {
                    row.addProperty("passed", false);
                    row.addProperty("error", failure.getClass().getName() + ": " + failure.getMessage());
                    failed++;
                }
                items.add(row);
            }
            report.add("items", items);
            JsonArray blocks = new JsonArray();
            for (ResourceLocation id : ForgeRegistries.BLOCKS.getKeys().stream().sorted(Comparator.comparing(ResourceLocation::toString)).toList()) {
                if (id.getNamespace().equals("minecraft")) continue;
                JsonObject row = new JsonObject();
                var block = ForgeRegistries.BLOCKS.getValue(id);
                row.addProperty("id", id.toString());
                row.addProperty("possible_states", block.getStateDefinition().getPossibleStates().size());
                blocks.add(row);
            }
            report.add("blocks", blocks);
            JsonArray entities = new JsonArray();
            for (ResourceLocation id : ForgeRegistries.ENTITY_TYPES.getKeys().stream().sorted(Comparator.comparing(ResourceLocation::toString)).toList())
                if (!id.getNamespace().equals("minecraft")) entities.add(id.toString());
            report.add("entity_types", entities);
            report.addProperty("default_stack_passed", passed);
            report.addProperty("default_stack_failed", failed);
            report.add("player_schema", playerSchema(FakePlayerFactory.getMinecraft(event.getServer().overworld())));
            JsonArray carts = new JsonArray();
            for (String[] cart : new String[][] {
                    {"moreminecarts:flag_cart", "com.alc.moreminecarts.entities.FlagCartEntity", "DISPLAY_TYPE"},
                    {"moreminecarts:tank_cart", "com.alc.moreminecarts.entities.TankCartEntity", "FLUID_TAG"}}) {
                Entity entity = ForgeRegistries.ENTITY_TYPES.getValue(new ResourceLocation(cart[0])).create(event.getServer().overworld());
                if (entity == null) throw new IllegalStateException("Cannot construct QA cart: " + cart[0]);
                JsonObject cartSchema = schema(entity, new String[][] {{cart[1], cart[2]}});
                cartSchema.addProperty("entity_type", cart[0]);
                carts.add(cartSchema);
                entity.discard();
            }
            report.add("minecart_schemas", carts);
            write("catalog-server.json", report);
            System.out.println("PSA_CATALOG_PROBE SUMMARY items=" + items.size() + " blocks=" + blocks.size()
                    + " entity_types=" + entities.size() + " default_stack_passed=" + passed + " failed=" + failed);
        } catch (Throwable failure) {
            System.err.println("PSA_CATALOG_PROBE FAILED");
            failure.printStackTrace();
        } finally {
            event.getServer().halt(false);
        }
    }
}
