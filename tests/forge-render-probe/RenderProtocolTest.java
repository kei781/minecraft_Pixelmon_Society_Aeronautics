package dev.psa.renderprobe;

import java.util.List;
import java.util.ArrayList;
import java.util.UUID;
import static dev.psa.renderprobe.RenderProtocol.*;

/** Run directly with JDK17; real rendering still needs the authenticated client. */
public final class RenderProtocolTest {
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
    private static void rejects(Runnable action) {
        try { action.run(); } catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("Invalid protocol input accepted");
    }
    private static Token token(int id, UUID uuid, String item) {
        return new Token(id, uuid, item, "minecraft:item", "net.minecraft.world.entity.item.ItemEntity", false);
    }
    public static void main(String[] args) {
        UUID player = UUID.randomUUID(), run = UUID.randomUUID(), entity = UUID.randomUUID();
        Token token = token(65536, entity, "pixelmon:poke_ball");
        Batch expected = new Batch(run, 7, List.of(token));
        check(matches(player, player, expected, new Ack(expected, 1, 0)));
        check(!matches(UUID.randomUUID(), player, expected, new Ack(expected, 1, 0)));
        check(!matches(player, player, expected, new Ack(new Batch(UUID.randomUUID(), 7, List.of(token)), 1, 0)));
        check(!matches(player, player, expected, new Ack(new Batch(run, 8, List.of(token)), 1, 0)));
        for (Token changed : List.of(token(65535, entity, token.itemId()),
                token(token.entityId(), UUID.randomUUID(), token.itemId()), token(token.entityId(), entity, "minecraft:stone"),
                new Token(token.entityId(), entity, token.itemId(), "create:package", token.entityClass(), false),
                new Token(token.entityId(), entity, token.itemId(), token.entityType(), "some.OtherEntity", false),
                new Token(token.entityId(), entity, token.itemId(), token.entityType(), token.entityClass(), true)))
            check(!matches(player, player, expected, new Ack(new Batch(run, 7, List.of(changed)), 1, 0)));
        rejects(() -> new Batch(run, 0, List.of()));
        rejects(() -> new Batch(run, 0, List.of(token, token)));
        rejects(() -> new Batch(run, 0, List.of(token, token(1, entity, token.itemId()))));
        rejects(() -> new Batch(run, -1, List.of(token)));
        var four = new ArrayList<Token>();
        for (int i = 0; i < 4; i++) four.add(token(i, UUID.randomUUID(), "minecraft:stone"));
        check(new Batch(run, 0, four).tokens().size() == 4);
        var five = new ArrayList<>(four); five.add(token(9, UUID.randomUUID(), "minecraft:stone"));
        rejects(() -> new Batch(run, 0, five));
        check(token(1, entity, "m:" + "a".repeat(254)).itemId().length() == 256);
        rejects(() -> token(1, entity, "m:" + "a".repeat(255)));
        rejects(() -> token(-1, entity, token.itemId())); rejects(() -> token(1, entity, "invalid"));
        rejects(() -> new Ack(expected, -1, 0)); rejects(() -> new Ack(expected, 1, -1));
        rejects(() -> new Ack(expected, 2, 0)); rejects(() -> new Ack(expected, 0, 1));
        check(new Ack(expected, 0, 0).modelObservedMask() == 0); // transported as unverified
        check(checkedCount(1) == 1 && checkedCount(4) == 4);
        rejects(() -> checkedCount(0)); rejects(() -> checkedCount(5));
        System.out.println("PSA_RENDER_PROTOCOL_PASS sender/identity/subtype/nonce/batch and exact1/4/5/256/257/mask boundaries");
    }
}
