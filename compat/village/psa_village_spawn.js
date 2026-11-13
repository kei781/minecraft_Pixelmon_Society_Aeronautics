// PSA village start compatibility (server side, KubeJS).
//
// Pixelmon cancels the world-spawn event after choosing the nearest village,
// but Society's Biome Spawn Point still receives the cancelled event and moves
// the spawn to the centre of one of its allowed biomes. The result is a start
// with no village and no Pokemon Center nearby.
//
// For a newly created world this script keeps Society's biome choice as the
// search origin and moves the world spawn to the nearest plains village whose
// real jigsaw assembly contains a Pokemon Center. Existing worlds are never
// changed automatically; an operator can run `/psa_village_spawn apply`.
//
// Rhino note: `const` only at function top level; nested blocks use `let`.
// KubeJS exposes the game time of a level as getTime().
(() => {
  const STATE_KEY = 'psa_village_spawn';
  const FRESH_WORLD_TICKS = 200;
  const SEARCH_RINGS = 8;
  const START_VILLAGES = ['minecraft:village_plains'];
  const REQUIRED_PIECE = 'pokecenter';
  const report = data => console.info('PSA_VILLAGE_SPAWN ' + JSON.stringify(data));
  const idOf = holder => '' + holder.unwrapKey().get().location();

  // Nearest allowed village (by its town centre) around `origin` whose structure start, as the
  // world saved it or will generate it, contains a Pokemon Center.
  const findStartVillage = (server, origin) => {
    const Registries = Java.loadClass('net.minecraft.core.registries.Registries');
    const ResourceLocation = Java.loadClass('net.minecraft.resources.ResourceLocation');
    const ChunkStatus = Java.loadClass('net.minecraft.world.level.chunk.ChunkStatus');
    const level = server.overworld();
    const source = level.getChunkSource();
    const villages = server.registryAccess().registryOrThrow(Registries.STRUCTURE_SET).get(new ResourceLocation('minecraft:villages'));
    const placement = villages.placement();
    const spacing = placement.spacing();
    const originRegionX = Math.floor((origin.getX() >> 4) / spacing);
    const originRegionZ = Math.floor((origin.getZ() >> 4) / spacing);
    const entries = [];
    const best = { village: null, distance: -1, examined: 0 };
    const visit = (regionX, regionZ) => {
      const chunk = placement.getPotentialStructureChunk(level.getSeed(), regionX * spacing, regionZ * spacing);
      if (!placement.isStructureChunk(source.getGeneratorState(), chunk.x, chunk.z)) return;
      const starts = level.getChunk(chunk.x, chunk.z, ChunkStatus.STRUCTURE_STARTS);
      entries.forEach(holder => {
        let start = starts.getStartForStructure(holder.value());
        if (start === null || !start.isValid()) return;
        best.examined++;
        let equipped = false;
        let first = null;
        // Iterate only: the piece list is an immutable JDK list whose get() this engine cannot call.
        start.getPieces().forEach(piece => {
          let name = '' + piece;
          if (first === null) first = piece;
          try { name = '' + piece.getElement(); } catch (ignored) { }
          if (name.indexOf(REQUIRED_PIECE) >= 0) equipped = true;
        });
        if (!equipped || first === null) return;
        let centre = first.getBoundingBox().getCenter();
        let dx = centre.getX() - origin.getX();
        let dz = centre.getZ() - origin.getZ();
        let distance = Math.sqrt(dx * dx + dz * dz);
        if (best.village === null || distance < best.distance) {
          best.village = { structure: idOf(holder), chunk_x: chunk.x, chunk_z: chunk.z, centre_x: centre.getX(), centre_z: centre.getZ() };
          best.distance = distance;
        }
      });
    };
    villages.structures().forEach(entry => {
      if (START_VILLAGES.indexOf(idOf(entry.structure())) >= 0) entries.push(entry.structure());
    });
    for (let ring = 0; ring <= SEARCH_RINGS; ring++) {
      // Every village of ring k is at least (k - 1) * spacing chunks away, so stop once that exceeds the best.
      if (best.village !== null && (ring - 1) * spacing * 16 >= best.distance) break;
      for (let dx = -ring; dx <= ring; dx++) {
        for (let dz = -ring; dz <= ring; dz++) {
          if (Math.max(Math.abs(dx), Math.abs(dz)) !== ring) continue;
          visit(originRegionX + dx, originRegionZ + dz);
        }
      }
    }
    return best;
  };

  // A vanilla-valid respawn block in or next to the town centre chunk.
  const groundNear = (level, village) => {
    const ChunkPos = Java.loadClass('net.minecraft.world.level.ChunkPos');
    const PlayerRespawnLogic = Java.loadClass('net.minecraft.server.level.PlayerRespawnLogic');
    const chunkX = village.centre_x >> 4;
    const chunkZ = village.centre_z >> 4;
    for (let ring = 0; ring <= 2; ring++) {
      for (let dx = -ring; dx <= ring; dx++) {
        for (let dz = -ring; dz <= ring; dz++) {
          if (Math.max(Math.abs(dx), Math.abs(dz)) !== ring) continue;
          let ground = PlayerRespawnLogic.getSpawnPosInChunk(level, new ChunkPos(chunkX + dx, chunkZ + dz));
          if (ground !== null) return ground;
        }
      }
    }
    return null;
  };

  const apply = (server, reason) => {
    const level = server.overworld();
    const origin = level.getSharedSpawnPos();
    const result = { reason: reason, origin: [origin.getX(), origin.getY(), origin.getZ()], changed: false };
    if (!server.getWorldData().worldGenOptions().generateStructures()) {
      result.outcome = 'structures-disabled';
      return result;
    }
    const found = findStartVillage(server, origin);
    result.villages_examined = found.examined;
    if (found.village === null) {
      result.outcome = 'no-equipped-village-in-range';
      return result;
    }
    const ground = groundNear(level, found.village);
    result.village = found.village;
    result.village_distance = Math.round(found.distance);
    if (ground === null) {
      result.outcome = 'no-safe-ground';
      return result;
    }
    level.setDefaultSpawnPos(ground, 0.0);
    result.outcome = 'moved-to-village';
    result.changed = true;
    result.spawn = [ground.getX(), ground.getY(), ground.getZ()];
    return result;
  };

  const decide = (server, reason) => {
    let result;
    try {
      result = apply(server, reason);
    } catch (failure) {
      // Leave the spawn Society selected; never fail server start for this.
      result = { reason: reason, changed: false, outcome: 'error', error: '' + failure };
    }
    server.persistentData.putString(STATE_KEY, result.outcome);
    report(result);
    return result;
  };

  ServerEvents.loaded(event => {
    const server = event.server;
    if (server.persistentData.contains(STATE_KEY)) return;
    if (server.overworld().getTime() > FRESH_WORLD_TICKS) {
      server.persistentData.putString(STATE_KEY, 'existing-world-unchanged');
      report({ reason: 'server-start', changed: false, outcome: 'existing-world-unchanged' });
      return;
    }
    decide(server, 'new-world');
  });

  ServerEvents.commandRegistry(event => {
    const Commands = event.commands;
    const Component = Java.loadClass('net.minecraft.network.chat.Component');
    event.register(Commands.literal('psa_village_spawn').requires(source => source.hasPermission(3))
      .then(Commands.literal('status').executes(context => {
        const server = context.getSource().getServer();
        const spawn = server.overworld().getSharedSpawnPos();
        const state = server.persistentData.contains(STATE_KEY) ? server.persistentData.getString(STATE_KEY) : 'undecided';
        context.getSource().sendSystemMessage(Component.literal(
          'PSA village spawn: ' + state + ', world spawn ' + spawn.getX() + ' ' + spawn.getY() + ' ' + spawn.getZ()));
        return 1;
      }))
      .then(Commands.literal('apply').executes(context => {
        const result = decide(context.getSource().getServer(), 'operator-command');
        context.getSource().sendSystemMessage(Component.literal('PSA village spawn: ' + JSON.stringify(result)));
        return result.changed ? 1 : 0;
      })));
  });
})();
