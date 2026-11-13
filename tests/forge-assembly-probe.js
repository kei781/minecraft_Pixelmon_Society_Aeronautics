// Isolated server test only. Do not include this in the player/server release.
//
// Console commands for the physics-assembly checks of tools/run_village_probe.py.
//
//   psa_probe_sublevels      the block entities that now live inside Sable sub-levels, with the
//                            start of their saved data, so a moved inventory can be inspected.
//   psa_probe_assembly_next  takes the next BATCH registered blocks that have a block entity (id
//                            order; `assembly_sweep_skip` of tests/forge-coexistence-checks.json
//                            is left out). Each is placed in the prepared test cell, given one marked
//                            item (through its item handler, otherwise through its saved item
//                            list), assembled alone with the port's own `sable assemble area`, and
//                            the marked item is looked for on the ground and in the moved block.
//
// A marked item that lies on the ground and is also inside the moved block entity exists twice.
// The driver prepares the cell: a force-loaded chunk and a floor one block below, outside the
// assembled area, so dropped stacks stay where they can be counted.
//
// Output: one `PSA_ASSEMBLY_PROBE <json>` line per command, after one `PSA_ASSEMBLY_PROBE_AT
// <number> <block>` line per block.
//
// Rhino note: `const` is only used at function top level; nested blocks use `let`.
(() => {
  const CELL = [8, 200, 136];
  const BATCH = 40;
  const MARK = 'psa_assembly_marker';
  const MARKER_ITEMS = ['minecraft:diamond', 'minecraft:wheat', 'minecraft:coal', 'minecraft:iron_ingot',
    'minecraft:paper', 'minecraft:bucket', 'minecraft:wheat_seeds', 'minecraft:glass_bottle'];
  const ITEM_LISTS = ['items', 'inventory', 'inv', 'contents', 'stacks'];
  // Keys under which block entities commonly save one displayed or processed stack. A block entity
  // without contents usually saves no such key, so these are offered blindly; unread keys are ignored.
  const SINGLE_ITEMS = ['Item', 'item', 'ItemIn', 'ItemStack', 'itemStack', 'Stack', 'stack', 'RecordItem', 'Book',
    'HeldItem', 'heldItem', 'DisplayItem', 'displayItem', 'StoredItem', 'storedItem', 'Input', 'input', 'Output', 'output'];
  const state = { ids: null, next: 0 };
  const str = value => '' + value;

  const blockEntitiesOf = subLevel => {
    const found = [];
    subLevel.getPlot().getLoadedChunks().forEach(holder => {
      holder.getChunk().getBlockEntities().values().forEach(blockEntity => { found.push(blockEntity); });
    });
    return found;
  };

  const subLevelsOf = level => {
    const found = [];
    level.sable$getPlotContainer().getAllSubLevels().forEach(subLevel => { found.push(subLevel); });
    return found;
  };

  const markedTag = (classes, id) => classes.TagParser.parseTag('{id:"' + id + '",Count:1b,tag:{' + MARK + ':1b}}');

  const markedStack = (classes, id) => classes.ItemStack.of(markedTag(classes, id));

  const holdsMarker = blockEntity => str(blockEntity.saveWithoutMetadata()).indexOf(MARK) >= 0;

  // Returns [an item handler exists, the marked item was accepted].
  const insertByHandler = (classes, blockEntity) => {
    const sides = [null];
    const directions = classes.Direction.values();
    let exists = false;
    for (let d = 0; d < directions.length; d++) sides.push(directions[d]);
    for (let s = 0; s < sides.length; s++) {
      let handler = blockEntity.getCapability(classes.ForgeCapabilities.ITEM_HANDLER, sides[s]).orElse(null);
      if (handler === null) continue;
      exists = true;
      let slots = handler.getSlots();
      for (let m = 0; m < MARKER_ITEMS.length; m++) {
        for (let slot = 0; slot < slots; slot++) {
          if (handler.insertItem(slot, markedStack(classes, MARKER_ITEMS[m]), false).isEmpty()) return [true, true];
        }
      }
    }
    return [exists, false];
  };

  // Adds the marked item as slot 0 of the first saved item list (ItemStackHandler and vanilla
  // container layouts, also nested), for inventories that refuse the marker items as input.
  const injectIntoSavedList = (classes, tag, depth) => {
    const keys = [];
    tag.getAllKeys().forEach(key => { keys.push(str(key)); });
    for (let i = 0; i < keys.length; i++) {
      let child = tag.get(keys[i]);
      let type = child.getId();
      if (type === 9) {
        if (ITEM_LISTS.indexOf(keys[i].toLowerCase()) >= 0 && (child.isEmpty() || child.getElementType() === 10)) {
          let entry = markedTag(classes, MARKER_ITEMS[0]);
          entry.putByte('Slot', 0);
          child.add(entry);
          return true;
        }
        if (depth > 0 && !child.isEmpty() && child.getElementType() === 10) {
          for (let j = 0; j < child.size(); j++) {
            if (injectIntoSavedList(classes, child.getCompound(j), depth - 1)) return true;
          }
        }
      } else if (type === 10 && depth > 0) {
        if (injectIntoSavedList(classes, child, depth - 1)) return true;
      }
    }
    return false;
  };

  // Removes every item entity near the cell and returns how many marked items were among them.
  const sweepItems = (classes, world) => {
    let marked = 0;
    world.level.getEntitiesOfClass(classes.ItemEntity, world.box).forEach(entity => {
      if (str(entity.saveWithoutId(new classes.CompoundTag())).indexOf(MARK) >= 0) marked += 1;
      entity.discard();
    });
    return marked;
  };

  const clearCell = (classes, world) => {
    const air = classes.Blocks.AIR.defaultBlockState();
    for (let dy = 0; dy <= 2; dy++) {
      for (let dx = -1; dx <= 1; dx++) {
        for (let dz = -1; dz <= 1; dz++) {
          let position = world.pos.offset(dx, dy, dz);
          if (!world.level.getBlockState(position).isAir()) {
            world.level.removeBlockEntity(position);
            world.level.setBlock(position, air, 18);
          }
        }
      }
    }
    sweepItems(classes, world);
  };

  const testBlock = (classes, world, id) => {
    const record = { id: id };
    const skip = (global.psaProbeSpec || {}).assembly_sweep_skip || {};
    if (skip[id] !== undefined) {
      record.outcome = 'skipped';
      return record;
    }
    const block = classes.ForgeRegistries.BLOCKS.getValue(new classes.ResourceLocation(id));
    world.level.setBlock(world.pos, block.defaultBlockState(), 18);
    const blockEntity = world.level.getBlockEntity(world.pos);
    if (blockEntity === null) {
      record.outcome = 'no block entity after placing';
      return record;
    }
    record.block_class = str(block.getClass().getName());
    record.block_entity_class = str(blockEntity.getClass().getName());
    record.clearable = blockEntity instanceof classes.Clearable;
    const inserted = insertByHandler(classes, blockEntity);
    record.item_handler = inserted[0];
    let given = inserted[1] ? 'item handler' : null;
    if (given === null) {
      let tag = blockEntity.saveWithoutMetadata();
      if (injectIntoSavedList(classes, tag, 3)) {
        blockEntity.load(tag);
        given = 'saved item list';
      }
    }
    if (!holdsMarker(blockEntity)) {
      let tag = blockEntity.saveWithoutMetadata();
      SINGLE_ITEMS.forEach(key => { if (!tag.contains(key)) tag.put(key, markedTag(classes, MARKER_ITEMS[0])); });
      blockEntity.load(tag);
      given = 'saved single item';
    }
    if (!holdsMarker(blockEntity)) {
      record.outcome = 'no inventory found for the marked item';
      return record;
    }
    record.marker_given_by = given;
    const known = {};
    subLevelsOf(world.level).forEach(subLevel => { known[str(subLevel.getUniqueId())] = true; });
    world.server.runCommandSilent('sable assemble area ' + CELL.join(' ') + ' ' + CELL.join(' '));
    record.left_behind = !world.level.getBlockState(world.pos).isAir();
    record.moved = false;
    record.in_moved_block = false;
    subLevelsOf(world.level).forEach(subLevel => {
      if (known[str(subLevel.getUniqueId())] === true) return;
      record.moved = true;
      blockEntitiesOf(subLevel).forEach(moved => { if (holdsMarker(moved)) record.in_moved_block = true; });
    });
    // Removed at once so the one-block test structure never reaches a physics tick. The port's own
    // command is used: the container methods for it are declared in a class that also names
    // client-only types, which hides them from scripts on a dedicated server.
    if (record.moved) world.server.runCommandSilent('sable remove @e');
    record.on_the_ground = sweepItems(classes, world);
    if (!record.moved) record.outcome = 'not assembled';
    else if (record.on_the_ground > 0 && record.in_moved_block) record.outcome = 'duplicated';
    else if (record.on_the_ground > 0) record.outcome = 'dropped, not moved';
    else if (record.in_moved_block) record.outcome = 'moved';
    else record.outcome = 'lost';
    return record;
  };

  const nextBatch = server => {
    const classes = {
      ResourceLocation: Java.loadClass('net.minecraft.resources.ResourceLocation'),
      ForgeRegistries: Java.loadClass('net.minecraftforge.registries.ForgeRegistries'),
      ForgeCapabilities: Java.loadClass('net.minecraftforge.common.capabilities.ForgeCapabilities'),
      Direction: Java.loadClass('net.minecraft.core.Direction'),
      BlockPos: Java.loadClass('net.minecraft.core.BlockPos'),
      Blocks: Java.loadClass('net.minecraft.world.level.block.Blocks'),
      Clearable: Java.loadClass('net.minecraft.world.Clearable'),
      ItemStack: Java.loadClass('net.minecraft.world.item.ItemStack'),
      ItemEntity: Java.loadClass('net.minecraft.world.entity.item.ItemEntity'),
      CompoundTag: Java.loadClass('net.minecraft.nbt.CompoundTag'),
      TagParser: Java.loadClass('net.minecraft.nbt.TagParser'),
      AABB: Java.loadClass('net.minecraft.world.phys.AABB')
    };
    const level = server.overworld();
    const world = {
      server: server, level: level,
      pos: new classes.BlockPos(CELL[0], CELL[1], CELL[2]),
      box: new classes.AABB(CELL[0] - 6, CELL[1] - 6, CELL[2] - 6, CELL[0] + 7, CELL[1] + 7, CELL[2] + 7)
    };
    const records = [];
    if (state.ids === null) {
      let ids = [];
      classes.ForgeRegistries.BLOCKS.getKeys().forEach(key => {
        if (classes.ForgeRegistries.BLOCKS.getValue(key).defaultBlockState().hasBlockEntity()) ids.push(str(key));
      });
      ids.sort();
      state.ids = ids;
    }
    const from = state.next;
    const to = Math.min(state.ids.length, from + BATCH);
    for (let index = from; index < to; index++) {
      let record;
      // Written before the block is placed: if placing it brings the server down, the log names it.
      console.info('PSA_ASSEMBLY_PROBE_AT ' + index + ' ' + state.ids[index]);
      try {
        record = testBlock(classes, world, state.ids[index]);
      } catch (failure) {
        record = { id: state.ids[index], outcome: 'error', error: str(failure).substring(0, 300) };
      }
      try {
        clearCell(classes, world);
      } catch (failure) {
        record.cleanup_error = str(failure).substring(0, 300);
      }
      records.push(record);
    }
    state.next = to;
    return { from: from, to: to, total: state.ids.length, done: to >= state.ids.length, records: records };
  };

  ServerEvents.commandRegistry(event => {
    const Commands = event.commands;
    event.register(Commands.literal('psa_probe_sublevels').requires(source => source.hasPermission(4))
      .executes(context => {
        const found = [];
        subLevelsOf(context.getSource().getServer().overworld()).forEach(subLevel => {
          blockEntitiesOf(subLevel).forEach(blockEntity => {
            let position = blockEntity.getBlockPos();
            found.push({ pos: [position.getX(), position.getY(), position.getZ()],
              data: str(blockEntity.saveWithoutMetadata()).substring(0, 3000) });
          });
        });
        console.info('PSA_PROBE_SUBLEVELS ' + JSON.stringify(found));
        return 1;
      }));
    event.register(Commands.literal('psa_probe_assembly_next').requires(source => source.hasPermission(4))
      .executes(context => {
        let result;
        try {
          result = nextBatch(context.getSource().getServer());
        } catch (failure) {
          result = { done: true, failed: str(failure).substring(0, 600) };
        }
        console.info('PSA_ASSEMBLY_PROBE ' + JSON.stringify(result));
        return 1;
      }));
  });
})();
