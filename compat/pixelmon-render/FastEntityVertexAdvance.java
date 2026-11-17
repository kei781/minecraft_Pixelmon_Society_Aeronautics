package dev.psa.pixelmonrender;

/** Optional base-cursor transition; a false return leaves all cursor state unchanged. */
public interface FastEntityVertexAdvance {
    boolean psa$tryAdvanceEntityBase();
}
