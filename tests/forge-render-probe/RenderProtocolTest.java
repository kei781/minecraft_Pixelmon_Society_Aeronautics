package dev.psa.renderprobe;

import java.util.List;
import java.util.UUID;
import static dev.psa.renderprobe.RenderProtocol.*;

/** Run directly with JDK17; real rendering still needs the authenticated client. */
public final class RenderProtocolTest {
    private static void check(boolean value) { if (!value) throw new AssertionError(); }
    private static void rejects(Runnable action) {
        try { action.run(); } catch (IllegalArgumentException expected) { return; }
        throw new AssertionError("Invalid protocol input accepted");
    }
    public static void main(String[] args) {
        UUID player = UUID.randomUUID(), run = UUID.randomUUID(), entity = UUID.randomUUID();
        Token token = new Token(65536, entity, "pixelmon:poke_ball");
        Batch expected = new Batch(run, 7, List.of(token));
        check(matches(player, player, expected, new Ack(expected, 0)));
        check(!matches(UUID.randomUUID(), player, expected, new Ack(expected, 0)));
        check(!matches(player, player, expected, new Ack(new Batch(UUID.randomUUID(), 7, List.of(token)), 0)));
        check(!matches(player, player, expected, new Ack(new Batch(run, 8, List.of(token)), 0)));
        for (Token changed : List.of(new Token(65535, entity, token.itemId()),
                new Token(token.entityId(), UUID.randomUUID(), token.itemId()),
                new Token(token.entityId(), entity, "minecraft:stone")))
            check(!matches(player, player, expected, new Ack(new Batch(run, 7, List.of(changed)), 0)));
        rejects(() -> new Batch(run, 0, List.of()));
        rejects(() -> new Batch(run, 0, List.of(token, token)));
        rejects(() -> new Batch(run, -1, List.of(token)));
        rejects(() -> new Ack(expected, 2));
        rejects(() -> new Token(-1, entity, token.itemId()));
        rejects(() -> new Token(1, entity, "invalid"));
        System.out.println("PSA_RENDER_PROTOCOL_PASS identity/nonce/batch/sender/bounds negative controls");
    }
}
