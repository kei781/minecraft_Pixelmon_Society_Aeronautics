// Isolated server test only. Do not include this in the player/server release.
//
// Reads the village worldgen state (and the shared chest loot) that the running game actually loaded and
// assembles real villages with the game's own Structure.generate path (the
// same call /place structure uses), at the exact chunks the vanilla
// `minecraft:villages` placement would choose. Nothing is placed in the world
// by this script; tools/run_village_probe.py generates selected villages
// afterwards and reads the saved chunks back.
//
// Output: one `PSA_VILLAGE_PROBE <kind> <json>` line per record, then
// `PSA_VILLAGE_PROBE_DONE`. Any exception ends with `PSA_VILLAGE_PROBE_FAILED`.
//
// Rhino note: `const` is only used at function top level; nested blocks use
// `let`, because this engine rejects block-level `const` as a redeclaration.
(() => {
  const TARGET_PER_STRUCTURE = 30;
  const MAX_REGION_RADIUS = 60;
  const TOWN_CENTRES = {
    plains: ['plains_fountain_01', 'plains_meeting_point_1', 'plains_meeting_point_2', 'plains_meeting_point_3'],
    desert: ['desert_meeting_point_1', 'desert_meeting_point_2', 'desert_meeting_point_3'],
    savanna: ['savanna_meeting_point_1', 'savanna_meeting_point_2', 'savanna_meeting_point_3', 'savanna_meeting_point_4'],
    snowy: ['snowy_meeting_point_1', 'snowy_meeting_point_2', 'snowy_meeting_point_3'],
    taiga: ['taiga_meeting_point_1', 'taiga_meeting_point_2']
  };
  const emit = (kind, data) => console.info('PSA_VILLAGE_PROBE ' + kind + ' ' + JSON.stringify(data));
  const str = value => '' + value;
  const idOf = holder => str(holder.unwrapKey().get().location());
  const boxOf = box => [box.minX(), box.minY(), box.minZ(), box.maxX(), box.maxY(), box.maxZ()];

  const probeSpawn = (classes, world) => {
    const spawn = world.level.getSharedSpawnPos();
    const villageTag = world.structures.getTag(classes.StructureTags.VILLAGE).get();
    const villageTagIds = [];
    const nearest = world.generator.findNearestMapStructure(world.level, villageTag, spawn, 100, false);
    let nearestVillage = null;
    villageTag.forEach(holder => villageTagIds.push(idOf(holder)));
    if (nearest !== null) {
      let found = nearest.getFirst();
      let dx = found.getX() - spawn.getX();
      let dz = found.getZ() - spawn.getZ();
      nearestVillage = {
        structure: idOf(nearest.getSecond()), x: found.getX(), z: found.getZ(),
        horizontal_distance: Math.round(Math.sqrt(dx * dx + dz * dz))
      };
    }
    emit('spawn', {
      seed: str(world.seed), x: spawn.getX(), y: spawn.getY(), z: spawn.getZ(),
      biome: idOf(world.level.getBiome(spawn)),
      generate_structures: world.server.getWorldData().worldGenOptions().generateStructures(),
      village_tag: villageTagIds, nearest_village: nearestVillage
    });
    return spawn;
  };

  const probePools = (classes, world) => {
    const ids = [];
    world.pools.keySet().forEach(key => {
      let id = str(key);
      if (id.startsWith('minecraft:village/') || id.startsWith('pixelmon:village') || id.startsWith('pixelmon:npc/')) ids.push(id);
    });
    ids.sort();
    ids.forEach(id => {
      let pool = world.pools.get(new classes.ResourceLocation(id));
      let vanilla = {};
      pool.getShuffledTemplates(classes.RandomSource.create(1)).forEach(element => {
        let name = str(element);
        vanilla[name] = (vanilla[name] || 0) + 1;
      });
      // Lithostitched assembles from its own compiled list when present.
      let compiled = null;
      try {
        let entries = {};
        pool.getLithostitchedTemplates().stream().forEach(element => {
          let name = str(element);
          entries[name] = (entries[name] || 0) + 1;
        });
        compiled = entries;
      } catch (ignored) { }
      emit('pool', { id: id, total_weight: pool.size(), elements: vanilla, lithostitched_entries: compiled });
    });
  };

  const probeTemplates = (classes, world) => {
    Object.keys(TOWN_CENTRES).forEach(biome => {
      TOWN_CENTRES[biome].forEach(name => {
        let id = 'minecraft:village/' + biome + '/town_centers/' + name;
        let template = world.templates.getOrCreate(new classes.ResourceLocation(id));
        let size = template.getSize();
        let targets = {};
        template.filterBlocks(classes.BlockPos.ZERO, new classes.StructurePlaceSettings(), classes.Blocks.JIGSAW).forEach(info => {
          let pool = str(info.nbt().getString('pool'));
          targets[pool] = (targets[pool] || 0) + 1;
        });
        emit('template', { id: id, size: [size.getX(), size.getY(), size.getZ()], jigsaw_pools: targets });
      });
    });
  };

  // Registry ids as the game loaded them, in parts of 1,500 with the total, so a missing part shows.
  const probeRegistries = (classes, world) => {
    const BuiltInRegistries = Java.loadClass('net.minecraft.core.registries.BuiltInRegistries');
    const LootDataType = Java.loadClass('net.minecraft.world.level.storage.loot.LootDataType');
    const Registries = Java.loadClass('net.minecraft.core.registries.Registries');
    const sources = {
      block: BuiltInRegistries.BLOCK.keySet(),
      entity_type: BuiltInRegistries.ENTITY_TYPE.keySet(),
      template_pool: world.pools.keySet(),
      structure: world.structures.keySet(),
      processor_list: world.access.registryOrThrow(Registries.PROCESSOR_LIST).keySet(),
      loot_table: world.server.getLootData().getKeys(LootDataType.TABLE)
    };
    Object.keys(sources).forEach(name => {
      let ids = [];
      sources[name].forEach(key => ids.push(str(key)));
      ids.sort();
      for (let offset = 0; offset < ids.length; offset += 1500) {
        emit('registry', { name: name, total: ids.length, offset: offset, ids: ids.slice(offset, offset + 1500) });
      }
    });
  };

  // Roll chest tables through the game's real loot path (Forge global loot modifiers and LootJS
  // included) and count the stacks by item id.
  const probeLoot = (classes, world, spec) => {
    const BuiltInRegistries = Java.loadClass('net.minecraft.core.registries.BuiltInRegistries');
    const LootParamsBuilder = Java.loadClass('net.minecraft.world.level.storage.loot.LootParams$Builder');
    const LootContextParams = Java.loadClass('net.minecraft.world.level.storage.loot.parameters.LootContextParams');
    const LootContextParamSets = Java.loadClass('net.minecraft.world.level.storage.loot.parameters.LootContextParamSets');
    const Vec3 = Java.loadClass('net.minecraft.world.phys.Vec3');
    (spec.loot_tables || []).forEach(check => {
      let table = world.server.getLootData().getLootTable(new classes.ResourceLocation(check.table));
      let items = {};
      let stacks = 0;
      for (let roll = 0; roll < check.rolls; roll++) {
        let params = new LootParamsBuilder(world.level)
          .withParameter(LootContextParams.ORIGIN, new Vec3(0.5, 64.0, 0.5)).create(LootContextParamSets.CHEST);
        table.getRandomItems(params).forEach(stack => {
          let item = str(BuiltInRegistries.ITEM.getKey(stack.getItem()));
          items[item] = (items[item] || 0) + 1;
          stacks++;
        });
      }
      emit('loot', { table: check.table, rolls: check.rolls, stacks: stacks, stacks_by_item: items });
    });
  };

  // Tag contents, crafting results, structure sets and sample structure assemblies named by the
  // check list that tools/run_village_probe.py installs as global.psaProbeSpec.
  const probeChecks = (classes, world, spec) => {
    const BuiltInRegistries = Java.loadClass('net.minecraft.core.registries.BuiltInRegistries');
    const Registries = Java.loadClass('net.minecraft.core.registries.Registries');
    const TagKey = Java.loadClass('net.minecraft.tags.TagKey');
    const ChunkPos = Java.loadClass('net.minecraft.world.level.ChunkPos');
    const ItemStack = Java.loadClass('net.minecraft.world.item.ItemStack');
    const NonNullList = Java.loadClass('net.minecraft.core.NonNullList');
    const RecipeType = Java.loadClass('net.minecraft.world.item.crafting.RecipeType');
    const TransientCraftingContainer = Java.loadClass('net.minecraft.world.inventory.TransientCraftingContainer');
    const SimpleContainer = Java.loadClass('net.minecraft.world.SimpleContainer');
    const registries = {
      item: [Registries.ITEM, BuiltInRegistries.ITEM], block: [Registries.BLOCK, BuiltInRegistries.BLOCK],
      entity_type: [Registries.ENTITY_TYPE, BuiltInRegistries.ENTITY_TYPE]
    };
    (spec.tags || []).forEach(check => {
      let pair = registries[check.registry];
      let values = [];
      pair[1].getTagOrEmpty(TagKey.create(pair[0], new classes.ResourceLocation(check.tag)))
        .forEach(holder => values.push(idOf(holder)));
      values.sort();
      emit('tag', { registry: check.registry, tag: check.tag, values: values });
    });
    (spec.crafting || []).forEach(check => {
      let stacks = NonNullList.withSize(9, ItemStack.EMPTY);
      let missing = [];
      for (let slot = 0; slot < 9; slot++) {
        let id = check.grid[Math.floor(slot / 3)][slot % 3];
        if (!id) continue;
        let key = new classes.ResourceLocation(id);
        if (!BuiltInRegistries.ITEM.containsKey(key)) { missing.push(id); continue; }
        stacks.set(slot, new ItemStack(BuiltInRegistries.ITEM.get(key)));
      }
      let container = new TransientCraftingContainer(null, 3, 3, stacks);
      let found = world.server.getRecipeManager().getRecipeFor(RecipeType.CRAFTING, container, world.level);
      let outcome = { name: check.name, missing_items: missing, recipe: null, result: null, count: 0 };
      if (found.isPresent()) {
        let made = found.get().assemble(container, world.access);
        outcome.recipe = str(found.get().getId());
        outcome.result = str(BuiltInRegistries.ITEM.getKey(made.getItem()));
        outcome.count = made.getCount();
      }
      emit('crafting', outcome);
    });
    (spec.cooking || []).forEach(check => {
      let key = new classes.ResourceLocation(check.input);
      let outcome = { name: check.name, recipe: null, result: null, count: 0 };
      if (BuiltInRegistries.ITEM.containsKey(key)) {
        let furnace = new SimpleContainer(1);
        furnace.setItem(0, new ItemStack(BuiltInRegistries.ITEM.get(key)));
        let found = world.server.getRecipeManager().getRecipeFor(
          BuiltInRegistries.RECIPE_TYPE.get(new classes.ResourceLocation(check.type)), furnace, world.level);
        if (found.isPresent()) {
          let made = found.get().assemble(furnace, world.access);
          outcome.recipe = str(found.get().getId());
          outcome.result = str(BuiltInRegistries.ITEM.getKey(made.getItem()));
          outcome.count = made.getCount();
        }
      }
      emit('cooking', outcome);
    });
    (spec.structure_sets || []).forEach(id => {
      let set = world.sets.get(new classes.ResourceLocation(id));
      let members = [];
      if (set !== null) set.structures().forEach(entry => members.push(idOf(entry.structure())));
      emit('structure_set', { id: id, structures: members });
    });
    (spec.assemble || []).forEach(check => {
      let structure = world.structures.get(new classes.ResourceLocation(check.structure));
      let samples = [];
      for (let index = 0; index < check.samples && structure !== null; index++) {
        // Any biome is accepted here: the question is what the structure consists of, not where it may stand.
        let chunk = new ChunkPos(check.chunk[0] + index * 40, check.chunk[1] + index * 40);
        let start = structure.generate(world.access, world.generator, world.generator.getBiomeSource(), world.randomState,
          world.templates, world.seed, chunk, 0, world.level, biome => true);
        let pieces = 0;
        let matched = 0;
        if (start.isValid()) {
          start.getPieces().forEach(piece => {
            let name = str(piece);
            try { name = str(piece.getElement()); } catch (ignored) { }
            pieces++;
            if (check.count_pieces_containing.some(text => name.indexOf(text) >= 0)) matched++;
          });
        }
        samples.push({ chunk: [chunk.x, chunk.z], valid: start.isValid(), pieces: pieces, matched: matched });
      }
      emit('assembly', { structure: check.structure, registered: structure !== null,
        count_pieces_containing: check.count_pieces_containing, samples: samples });
    });
  };

  const probeVillages = (classes, world, spawn) => {
    const villages = world.sets.get(new classes.ResourceLocation('minecraft:villages'));
    const placement = villages.placement();
    const spacing = placement.spacing();
    const entries = [];
    const found = {};
    const spawnRegionX = Math.floor((spawn.getX() >> 4) / spacing);
    const spawnRegionZ = Math.floor((spawn.getZ() >> 4) / spacing);
    const counters = { tried: 0, radius: 0 };
    const complete = () => entries.every(holder => found[idOf(holder)] >= TARGET_PER_STRUCTURE);
    const visit = (regionX, regionZ) => {
      const chunk = placement.getPotentialStructureChunk(world.seed, regionX * spacing, regionZ * spacing);
      if (!placement.isStructureChunk(world.structureState, chunk.x, chunk.z)) return;
      counters.tried++;
      entries.forEach(holder => {
        let id = idOf(holder);
        if (found[id] >= TARGET_PER_STRUCTURE) return;
        let structure = holder.value();
        let allowed = structure.biomes();
        let start = structure.generate(world.access, world.generator, world.generator.getBiomeSource(),
          world.randomState, world.templates, world.seed, chunk, 0, world.level, biome => allowed.contains(biome));
        if (!start.isValid()) return;
        found[id]++;
        let pieces = [];
        start.getPieces().forEach(piece => {
          let name = str(piece);
          try { name = str(piece.getElement()); } catch (ignored) { }
          pieces.push([name].concat(boxOf(piece.getBoundingBox())));
        });
        let box = start.getBoundingBox();
        let centre = box.getCenter();
        emit('village', {
          structure: id, chunk: [chunk.x, chunk.z], box: boxOf(box),
          biome: idOf(world.level.getBiome(centre)),
          spawn_distance: Math.round(Math.sqrt(Math.pow(centre.getX() - spawn.getX(), 2) + Math.pow(centre.getZ() - spawn.getZ(), 2))),
          pieces: pieces
        });
      });
    };
    villages.structures().forEach(entry => {
      entries.push(entry.structure());
      found[idOf(entry.structure())] = 0;
    });
    for (let radius = 0; radius <= MAX_REGION_RADIUS && !complete(); radius++) {
      counters.radius = radius;
      for (let dx = -radius; dx <= radius; dx++) {
        for (let dz = -radius; dz <= radius; dz++) {
          if (Math.max(Math.abs(dx), Math.abs(dz)) !== radius) continue;
          visit(spawnRegionX + dx, spawnRegionZ + dz);
        }
      }
    }
    emit('census', {
      target_per_structure: TARGET_PER_STRUCTURE, searched_region_radius: counters.radius,
      placement: { spacing: spacing, separation: placement.separation() },
      placement_chunks_tried: counters.tried, found: found
    });
  };

  const runProbe = event => {
    const Registries = Java.loadClass('net.minecraft.core.registries.Registries');
    const classes = {
      ResourceLocation: Java.loadClass('net.minecraft.resources.ResourceLocation'),
      RandomSource: Java.loadClass('net.minecraft.util.RandomSource'),
      StructureTags: Java.loadClass('net.minecraft.tags.StructureTags'),
      StructurePlaceSettings: Java.loadClass('net.minecraft.world.level.levelgen.structure.templatesystem.StructurePlaceSettings'),
      Blocks: Java.loadClass('net.minecraft.world.level.block.Blocks'),
      BlockPos: Java.loadClass('net.minecraft.core.BlockPos')
    };
    const server = event.server;
    const level = server.overworld();
    const access = server.registryAccess();
    const world = {
      server: server, level: level, access: access,
      generator: level.getChunkSource().getGenerator(),
      randomState: level.getChunkSource().randomState(),
      structureState: level.getChunkSource().getGeneratorState(),
      templates: server.getStructureManager(),
      seed: level.getSeed(),
      structures: access.registryOrThrow(Registries.STRUCTURE),
      pools: access.registryOrThrow(Registries.TEMPLATE_POOL),
      sets: access.registryOrThrow(Registries.STRUCTURE_SET)
    };
    const spawn = probeSpawn(classes, world);
    probePools(classes, world);
    probeTemplates(classes, world);
    const spec = global.psaProbeSpec || {};
    probeRegistries(classes, world);
    probeLoot(classes, world, spec);
    probeChecks(classes, world, spec);
    probeVillages(classes, world, spawn);
  };

  ServerEvents.loaded(event => {
    try {
      runProbe(event);
      console.info('PSA_VILLAGE_PROBE_DONE');
    } catch (failure) {
      console.error('PSA_VILLAGE_PROBE_FAILED ' + failure);
      throw failure;
    }
  });
})();
