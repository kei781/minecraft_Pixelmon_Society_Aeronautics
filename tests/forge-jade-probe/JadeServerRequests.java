package dev.psa.jadeprobe;

import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import net.minecraftforge.fml.loading.FMLPaths;

/** Counts original request callbacks only. No request, player, entity or data is fabricated. */
public final class JadeServerRequests {
    private static long blockRequests, blockCallbacks, entityRequests, entityCallbacks;
    private static long storageBlockRequests, storageBlockCallbacks, storageEntityRequests, storageEntityCallbacks;

    public static void began(boolean block, boolean storageLike) {
        if (block) { blockRequests++; if (storageLike) storageBlockRequests++; }
        else { entityRequests++; if (storageLike) storageEntityRequests++; }
        persist(block ? blockRequests == 1 || storageLike && storageBlockRequests == 1
                : entityRequests == 1 || storageLike && storageEntityRequests == 1);
    }

    public static void callbackReturned(boolean block, boolean storageLike) {
        if (block) { blockCallbacks++; if (storageLike) storageBlockCallbacks++; }
        else { entityCallbacks++; if (storageLike) storageEntityCallbacks++; }
        persist(block ? blockCallbacks == 1 || storageLike && storageBlockCallbacks == 1
                : entityCallbacks == 1 || storageLike && storageEntityCallbacks == 1);
    }

    private static void persist(boolean firstCategory) {
        long total = blockRequests + blockCallbacks + entityRequests + entityCallbacks;
        // First requests/callbacks and bounded cadence, no world mutation or sensitive identifiers.
        if (!firstCategory && total > 10 && total % 100 != 0) return;
        JsonObject value = new JsonObject();
        value.addProperty("scope", "Native Jade requests and forwarded native callback returns; not proof of client receipt. Storage-like is raw squared distance greater than 10000, not frame identity.");
        value.addProperty("block_requests", blockRequests); value.addProperty("block_callbacks_returned", blockCallbacks);
        value.addProperty("entity_requests", entityRequests); value.addProperty("entity_callbacks_returned", entityCallbacks);
        value.addProperty("storage_like_block_requests", storageBlockRequests); value.addProperty("storage_like_block_callbacks_returned", storageBlockCallbacks);
        value.addProperty("storage_like_entity_requests", storageEntityRequests); value.addProperty("storage_like_entity_callbacks_returned", storageEntityCallbacks);
        Path output = FMLPaths.GAMEDIR.get().resolve("logs/psa-jade-server-requests.json");
        Path temporary = output.resolveSibling("psa-jade-server-requests.json.tmp");
        try {
            Files.createDirectories(output.getParent());
            Files.writeString(temporary, new GsonBuilder().setPrettyPrinting().create().toJson(value));
            Files.move(temporary, output, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
        } catch (IOException failure) {
            throw new IllegalStateException("Could not persist native Jade request observation", failure);
        }
    }
}
