package dev.psa.renderprobe;

import java.util.ArrayList;
import java.util.Optional;
import java.util.function.Supplier;
import net.minecraft.network.FriendlyByteBuf;
import net.minecraft.resources.ResourceLocation;
import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.fml.DistExecutor;
import net.minecraftforge.network.NetworkDirection;
import net.minecraftforge.network.NetworkEvent;
import net.minecraftforge.network.NetworkRegistry;
import net.minecraftforge.network.simple.SimpleChannel;
import static dev.psa.renderprobe.RenderProtocol.*;

public final class RenderNetwork {
    public static final SimpleChannel CHANNEL = NetworkRegistry.newSimpleChannel(
            new ResourceLocation("psarenderprobe", "main"), () -> "1", "1"::equals, "1"::equals);
    private RenderNetwork() {}
    public static void register() {
        CHANNEL.registerMessage(0, Batch.class, RenderNetwork::encodeBatch, RenderNetwork::decodeBatch,
                RenderNetwork::receiveBatch, Optional.of(NetworkDirection.PLAY_TO_CLIENT));
        CHANNEL.registerMessage(1, Ack.class, (message, buffer) -> {
            encodeBatch(message.batch(), buffer); buffer.writeVarInt(message.missingModelMask());
        }, buffer -> new Ack(decodeBatch(buffer), buffer.readVarInt()), RenderNetwork::receiveAck,
                Optional.of(NetworkDirection.PLAY_TO_SERVER));
    }
    private static void encodeBatch(Batch message, FriendlyByteBuf buffer) {
        buffer.writeUUID(message.run()); buffer.writeVarInt(message.index()); buffer.writeVarInt(message.tokens().size());
        for (Token token : message.tokens()) {
            buffer.writeVarInt(token.entityId()); buffer.writeUUID(token.entityUuid()); buffer.writeUtf(token.itemId(), 256);
        }
    }
    private static Batch decodeBatch(FriendlyByteBuf buffer) {
        var run = buffer.readUUID(); int index = buffer.readVarInt(), count = buffer.readVarInt();
        if (count < 1 || count > 4) throw new IllegalArgumentException("Unbounded render packet");
        var tokens = new ArrayList<Token>(count);
        for (int i = 0; i < count; i++) tokens.add(new Token(buffer.readVarInt(), buffer.readUUID(), buffer.readUtf(256)));
        return new Batch(run, index, tokens);
    }
    private static void receiveBatch(Batch message, Supplier<NetworkEvent.Context> supplier) {
        var context = supplier.get();
        context.enqueueWork(() -> DistExecutor.unsafeRunWhenOn(Dist.CLIENT, () -> () -> RenderClient.accept(message)));
        context.setPacketHandled(true);
    }
    private static void receiveAck(Ack message, Supplier<NetworkEvent.Context> supplier) {
        var context = supplier.get();
        context.enqueueWork(() -> RenderProbe.acknowledge(context.getSender(), message));
        context.setPacketHandled(true);
    }
}
