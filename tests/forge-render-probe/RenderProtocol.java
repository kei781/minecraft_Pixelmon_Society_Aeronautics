package dev.psa.renderprobe;

import java.util.HashSet;
import java.util.List;
import java.util.UUID;

/** Pure bounded identity protocol; no world access or trust in client positions. */
public final class RenderProtocol {
    private RenderProtocol() {}
    public record Token(int entityId, UUID entityUuid, String itemId) {
        public Token {
            if (entityId < 0 || entityUuid == null || itemId == null
                    || !itemId.matches("[a-z0-9_.-]+:[a-z0-9_./-]+") || itemId.length() > 256)
                throw new IllegalArgumentException("Invalid entity token");
        }
    }
    public record Batch(UUID run, int index, List<Token> tokens) {
        public Batch {
            if (run == null || index < 0 || tokens == null || tokens.isEmpty() || tokens.size() > 4)
                throw new IllegalArgumentException("Invalid batch");
            tokens = List.copyOf(tokens);
            var ids = new HashSet<Integer>();
            var uuids = new HashSet<UUID>();
            for (var token : tokens)
                if (!ids.add(token.entityId()) || !uuids.add(token.entityUuid()))
                    throw new IllegalArgumentException("Duplicate entity token");
        }
    }
    public record Ack(Batch batch, int missingModelMask) {
        public Ack {
            if (batch == null || missingModelMask < 0 || missingModelMask >= (1 << batch.tokens().size()))
                throw new IllegalArgumentException("Invalid model mask");
        }
    }
    public static boolean matches(UUID sender, UUID selectedPlayer, Batch expected, Ack actual) {
        return sender != null && sender.equals(selectedPlayer) && expected != null
                && actual != null && expected.equals(actual.batch());
    }
}
