package dev.psa.renderprobe;

import java.util.HashSet;
import java.util.List;
import java.util.UUID;

/** Pure bounded identity protocol; no world access or trust in client positions. */
public final class RenderProtocol {
    private RenderProtocol() {}
    public record Token(int entityId, UUID entityUuid, String itemId, String entityType, String entityClass, boolean nativeReplacement) {
        public Token {
            if (entityId < 0 || entityUuid == null || itemId == null
                    || !registryId(itemId) || !registryId(entityType) || entityClass == null
                    || entityClass.length() > 256 || !entityClass.matches("[a-zA-Z0-9_.$]+"))
                throw new IllegalArgumentException("Invalid entity token");
        }
    }
    public record Batch(UUID run, int index, List<Token> tokens) {
        public Batch {
            if (run == null || index < 0 || tokens == null)
                throw new IllegalArgumentException("Invalid batch");
            checkedCount(tokens.size());
            tokens = List.copyOf(tokens);
            var ids = new HashSet<Integer>();
            var uuids = new HashSet<UUID>();
            for (var token : tokens)
                if (!ids.add(token.entityId()) || !uuids.add(token.entityUuid()))
                    throw new IllegalArgumentException("Duplicate entity token");
        }
    }
    public record Ack(Batch batch, int modelObservedMask, int missingModelMask) {
        public Ack {
            if (batch == null || missingModelMask < 0 || modelObservedMask < 0
                    || modelObservedMask >= (1 << batch.tokens().size()) || (missingModelMask & ~modelObservedMask) != 0)
                throw new IllegalArgumentException("Invalid model mask");
        }
    }
    private static boolean registryId(String value) {
        return value != null && value.length() <= 256 && value.matches("[a-z0-9_.-]+:[a-z0-9_./-]+");
    }
    public static int checkedCount(int count) {
        if (count < 1 || count > 4) throw new IllegalArgumentException("Unbounded render packet");
        return count;
    }
    public static boolean matches(UUID sender, UUID selectedPlayer, Batch expected, Ack actual) {
        return sender != null && sender.equals(selectedPlayer) && expected != null
                && actual != null && expected.equals(actual.batch());
    }
}
