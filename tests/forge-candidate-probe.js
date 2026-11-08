// Isolated server test only. Do not include this in the player/server release.
ServerEvents.loaded(event => {
  const source = event.server.createCommandSourceStack();
  const node = event.server.getCommands().getDispatcher().getRoot().getChild('sable');
  if (node === null) throw new Error('PSA: Sable command was not registered');
  const ordinaryDenied = !node.canUse(source.withPermission(0));
  const operatorAllowed = node.canUse(source.withPermission(2));
  console.info('PSA_SABLE_COMMAND_PERMISSIONS ordinaryDenied=' + ordinaryDenied + ' operatorAllowed=' + operatorAllowed);
  if (!ordinaryDenied || !operatorAllowed) throw new Error('PSA: unsafe Sable command permissions');
  const level = event.server.overworld();
  const chunk = level.getChunk(0, 0);
  const queue = chunk.leavesbegone$getRandomBlockTicks();
  if (queue === null) throw new Error('PSA: missing leaf ticker after FULL chunk load');
  const BlockPos = Java.loadClass('net.minecraft.core.BlockPos');
  const Blocks = Java.loadClass('net.minecraft.world.level.block.Blocks');
  const ScheduledTick = Java.loadClass('net.minecraft.world.ticks.ScheduledTick');
  const pos = new BlockPos(12, 121, 12);
  const seeded = event.server.persistentData.getBoolean('psa_leaf_ticker_seeded_v3');
  if (seeded) {
    const retained = queue.hasScheduledTick(pos, Blocks.OAK_LEAVES);
    console.info('PSA_SAVED_LEAF_TICK_RETAINED=' + retained);
    if (!retained) throw new Error('PSA: saved leaf tick missing');
  } else {
    // This test uses a newly created world. Absolute tick 1,000,000 is in
    // its future and keeps the serialized delay inside the int range.
    queue.schedule(new ScheduledTick(Blocks.OAK_LEAVES, pos, 1000000, 1));
    event.server.persistentData.putBoolean('psa_leaf_ticker_seeded_v3', true);
    console.info('PSA_LEAF_TICK_SEEDED=' + queue.hasScheduledTick(pos, Blocks.OAK_LEAVES));
  }
});
