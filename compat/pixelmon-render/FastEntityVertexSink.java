package dev.psa.pixelmonrender;

/** Returns false before mutation when the original consumer must handle this vertex. */
public interface FastEntityVertexSink {
    boolean psa$tryEntityVertex(float x, float y, float z, float red, float green,
            float blue, float alpha, float u, float v, int overlay, int light,
            float nx, float ny, float nz);
}
