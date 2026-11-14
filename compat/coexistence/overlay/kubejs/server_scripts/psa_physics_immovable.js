// PSA physics-assembly protection for Society's immovable blocks (server side, KubeJS).
//
// Society keeps its machines out of Create contraptions with the block tags create:non_movable and
// c:relocation_not_supported. The Aeronautics physics assembler tests only simulated:non_movable,
// which ships empty, so those machines could be lifted into a physics sub-level. This script adds
// to simulated:non_movable the blocks Society marks immovable and the Create blocks named below, and
// nothing else: the wider tags also hold Aeronautics' own bearings and winches and Create's tracks,
// which must stay movable.
//
// The two lists hold the same ids, in the same order, as Society 4.1.5A:
//   SOCIETY_IMMOVABLE: kubejs/server_scripts/tags/handleItemBlockFluidTags.js, the array applied
//     with immovableTags (file sha256 b8c332a711fbbafd2213738fa25ec866a45a9c2bdbce5601ab13918190f8a017).
//   SOCIETY_ARTISAN_MACHINES: kubejs/startup_scripts/globalArtisanMachineDefinitions.js, the ids
//     behind global.artisanMachineIds (file sha256 74b7a4006d36a817e21c1b1ee60db14f88ffba22f2043f89cc97c5d1d3fad302).
//   OTHER_IMMOVABLE: Create blocks outside Society's lists whose contents are also recorded in
//     the railway data. The train station holds a package and is registered in the railway graph.
//     A postbox linked to a station is mirrored, slot for slot, in that station's saved port list
//     (GlobalPackagePort.offlineBuffer), and only PackagePortBlockEntity.destroy() takes the port
//     out again. Moved the ordinary way each drops a second copy of its contents; moved with
//     sable:silent_assembly_removal (where they also are, for the console command) destroy() never
//     runs: the station's graph entry stays, and a port that outlives its postbox hands the
//     mirrored packages to the next train while the moved postbox still holds them, and swallows
//     the packages addressed to it. They stay on the ground instead.
// Society's startup scripts fill global.artisanMachineIds before any server script runs, so it is
// also read when the tag event fires; ids found only there are added as well and are reported.
// The two lists are added before the global is read, so a missing or unreadable global cannot
// drop them; society_global_read is true only when the global was iterated to its end.
//
// Constraints:
// - Only event.add is used. KubeJS first runs tag handlers against a recording event and replays the
//   recorded calls when the tags load; reading tag contents would switch that off and make the
//   result depend on the order of other handlers.
// - An id that is not a registered block is skipped by KubeJS without an error (strictTags is off).
// - Rhino: `const` only at function top level; callbacks use `let`.
(() => {
  const TAG = 'simulated:non_movable';
  const SOCIETY_IMMOVABLE = [
    'society:fish_pond',
    'society:coin_leaderboard',
    'society:iridium_clock',
    'society:golden_clock',
    'society:mana_clock',
    'society:sparkstone_recycler',
    'society:artisan_hopper',
    'society:mini_artisan_hopper',
    'society:auto_grabber',
    'society:auto_tapper',
    'society:auto_worm_farm',
    'society:feeding_trough',
    'society:fish_pond_basket',
    'society:growth_obelisk',
    'society:juice_inserter',
    'society:mana_milker',
    'society:mana_sprinkler',
    'society:quality_washer',
    'society:snow_melter',
    'society:villager_home',
    'society:shipping_bin_monitor',
    'society:ribbit_hut',
    'society:ribbit_hut_block',
    'society:roe_recycler',
    'society:pickling_can',
    'society:mana_fruit_crop',
    'shippingbin:smart_shipping_bin',
    'shippingbin:basic_shipping_bin',
    'society_trading:auto_trader',
    'society:fish_pond_manager',
    'society:fish_pond_hatchery',
    'society:caterpillar_box',
    'society:growth_obelisk_upper'
  ];
  const SOCIETY_ARTISAN_MACHINES = [
    'society:loom',
    'society:cheese_press',
    'society:wine_keg',
    'society:aging_cask',
    'society:ancient_cask',
    'society:crystalarium',
    'society:deluxe_worm_farm',
    'society:fish_smoker',
    'society:bait_maker',
    'society:dehydrator',
    'society:mayonnaise_machine',
    'society:preserves_jar',
    'society:seed_maker',
    'society:charging_rod',
    'society:espresso_machine',
    'society:tapper',
    'society:recycling_machine',
    'society:oil_maker',
    'society:mushroom_log'
  ];

  const OTHER_IMMOVABLE = [
    'create:track_station',
    'create:white_postbox',
    'create:orange_postbox',
    'create:magenta_postbox',
    'create:light_blue_postbox',
    'create:yellow_postbox',
    'create:lime_postbox',
    'create:pink_postbox',
    'create:gray_postbox',
    'create:light_gray_postbox',
    'create:cyan_postbox',
    'create:purple_postbox',
    'create:blue_postbox',
    'create:brown_postbox',
    'create:green_postbox',
    'create:red_postbox',
    'create:black_postbox'
  ];

  ServerEvents.tags('block', event => {
    const requested = [];
    const seen = {};
    const extra = [];
    const rejected = [];
    const request = id => {
      let key = '' + id;
      if (seen[key] === true) return false;
      seen[key] = true;
      requested.push(key);
      try {
        event.add(TAG, key);
      } catch (failure) {
        rejected.push(key);
      }
      return true;
    };
    SOCIETY_IMMOVABLE.forEach(id => { request(id); });
    SOCIETY_ARTISAN_MACHINES.forEach(id => { request(id); });
    OTHER_IMMOVABLE.forEach(id => { request(id); });
    let globalRead = false;
    try {
      let live = global.artisanMachineIds;
      if (live && typeof live.forEach === 'function') {
        live.forEach(id => { if (request(id)) extra.push('' + id); });
        globalRead = true;
      }
    } catch (failure) {
      globalRead = false;
    }
    console.info('PSA_PHYSICS_IMMOVABLE ' + JSON.stringify({
      tag: TAG, requested: requested.length, mirrored: SOCIETY_IMMOVABLE.length + SOCIETY_ARTISAN_MACHINES.length,
      other: OTHER_IMMOVABLE.length,
      society_global_read: globalRead, only_in_society_global: extra, rejected: rejected
    }));
  });
})();
