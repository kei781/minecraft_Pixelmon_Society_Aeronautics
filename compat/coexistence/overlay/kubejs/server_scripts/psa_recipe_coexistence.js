// priority: -100
// requires: pixelmon
//
// PSA recipe coexistence between Pixelmon and Society's mods (server side, KubeJS).
//
// Pixelmon and four Society-side mods (Whimsy Deco, Supplementaries, Botania, Oreganized) ship
// recipes that match the same input, so only one result of each pair could be made. This script
// separates every proven pair and keeps both results available:
//   - whimsy_deco:cast_iron_trapdoor and supplementaries:item_shelf take one extra ingredient, so
//     Pixelmon's Poke Ball bases keep their documented three-in-a-row recipes;
//   - pixelmon:box moves to an open box of seven paper, because Society uses Supplementaries
//     presents and their ring of eight paper stays as it is;
//   - Pixelmon's bridge block and end table stop accepting the Botania wood that Botania's own
//     slab and crafty crate recipes are made of, and keep their shape for all other wood;
//   - Pixelmon's silver block and silver ore cooking accept Pixelmon's own silver only, so
//     Oreganized silver can never turn into Pixelmon silver.
//
// Constraints:
// - Both header lines above are KubeJS file properties. A lower priority loads later, so this
//   handler runs after every recipe handler of Society (all of them use priority 0) and sees the
//   recipes Society's scripts removed. The file is skipped when Pixelmon is not installed.
// - A pair is touched only while both of its recipes are still active; a recipe that is missing,
//   disabled by a mod flag or removed by Society is left alone and reported as untouched.
// - A Society-side recipe is removed only after its replacement was created, never before.
// - Every narrowing is checked after it is applied; a failed check is reported, not hidden.
// - Nothing is stored: the recipe event starts from the data pack recipes on every reload.
// - Rhino: `const` only at function top level; callbacks use `let`.
(() => {
  // keep: the recipe whose grid stays; move: the colliding recipe that is registered again.
  const SEPARATED = [
    {
      keep: 'pixelmon:pokeball/base/iron_base',
      move: 'whimsy_deco:cast_iron_trapdoor',
      id: 'psa_coexistence:cast_iron_trapdoor',
      result: 'whimsy_deco:cast_iron_trapdoor',
      count: 1,
      pattern: ['III', ' N '],
      key: { I: 'minecraft:iron_ingot', N: 'minecraft:iron_nugget' },
      items: ['whimsy_deco:cast_iron_trapdoor', 'minecraft:iron_ingot', 'minecraft:iron_nugget']
    },
    {
      keep: 'pixelmon:pokeball/base/wooden_base',
      move: 'supplementaries:item_shelf',
      id: 'psa_coexistence:item_shelf',
      result: 'supplementaries:item_shelf',
      count: 2,
      pattern: ['SSS', ' T '],
      key: { S: '#minecraft:wooden_slabs', T: 'minecraft:stick' },
      items: ['supplementaries:item_shelf', 'minecraft:stick']
    },
    {
      keep: 'supplementaries:present',
      move: 'pixelmon:decor/household_items/box',
      id: 'psa_coexistence:box',
      result: 'pixelmon:box',
      count: 1,
      pattern: ['P P', 'P P', 'PPP'],
      key: { P: 'minecraft:paper' },
      items: ['pixelmon:box', 'minecraft:paper']
    }
  ];
  // recipe: the Pixelmon recipe that keeps its shape; rivals: the recipes that need one of the
  // tag's items for themselves; still: an item the narrowed recipe must go on accepting.
  const EXCLUDED = [
    {
      recipe: 'pixelmon:decor/building_infrastructure/bridge_block',
      tag: '#minecraft:logs',
      still: 'minecraft:oak_log',
      rivals: [
        { recipe: 'botania:livingwood_slab', item: 'botania:livingwood' },
        { recipe: 'botania:dreamwood_slab', item: 'botania:dreamwood' },
        { recipe: 'botania:stripped_livingwood_slab', item: 'botania:stripped_livingwood' },
        { recipe: 'botania:stripped_dreamwood_slab', item: 'botania:stripped_dreamwood' }
      ]
    },
    {
      recipe: 'pixelmon:decor/household_items/end_table',
      tag: '#minecraft:planks',
      still: 'minecraft:oak_planks',
      rivals: [
        { recipe: 'botania:crafty_crate', item: 'botania:dreamwood_planks' }
      ]
    }
  ];
  // recipe: the Pixelmon recipe; own: the only item its tag ingredient accepts afterwards;
  // foreign: the other mods' members of that tag in this pack.
  const OWN_ONLY = [
    {
      recipe: 'pixelmon:equipment/silver/silver_block',
      tag: '#forge:ingots/silver',
      own: 'pixelmon:silver_ingot',
      foreign: ['oreganized:silver_ingot']
    },
    {
      recipe: 'pixelmon:furnace/silver_ore',
      tag: '#forge:ores/silver',
      own: 'pixelmon:silver_ore',
      foreign: ['oreganized:silver_ore', 'oreganized:deepslate_silver_ore']
    },
    {
      recipe: 'pixelmon:blast_furnace/silver_ore',
      tag: '#forge:ores/silver',
      own: 'pixelmon:silver_ore',
      foreign: ['oreganized:silver_ore', 'oreganized:deepslate_silver_ore']
    }
  ];

  ServerEvents.recipes(event => {
    const report = { separated: [], narrowed: [], untouched: [], failed: [] };
    // Data pack recipes that are loaded and not removed by an earlier handler. Recipes added by
    // scripts are not counted, which is what the guards below need.
    const active = id => event.countRecipes({ id: id }) > 0;
    const accepts = (id, item) => event.countRecipes({ id: id, input: item }) > 0;

    const separate = entry => {
      if (!active(entry.keep) || !active(entry.move)) return 'untouched';
      let missing = entry.items.filter(id => !Item.exists(id));
      if (missing.length > 0) return 'untouched';
      let made = event.shaped(Item.of(entry.result, entry.count), entry.pattern, entry.key);
      made.id(entry.id);
      if ('' + made.getId() !== entry.id) throw 'replacement recipe was not created';
      event.remove({ id: entry.move });
      return 'separated';
    };

    const exclude = entry => {
      if (!active(entry.recipe)) return 'untouched';
      let taken = [];
      entry.rivals.forEach(rival => {
        if (active(rival.recipe) && accepts(entry.recipe, rival.item)) taken.push(rival.item);
      });
      if (taken.length === 0) return 'untouched';
      event.replaceInput({ id: entry.recipe }, entry.tag, Ingredient.of(entry.tag).subtract(Ingredient.of(taken)));
      taken.forEach(item => {
        if (accepts(entry.recipe, item)) throw 'still accepts ' + item;
      });
      if (!accepts(entry.recipe, entry.still)) throw 'no longer accepts ' + entry.still;
      return 'narrowed';
    };

    const restrict = entry => {
      if (!active(entry.recipe) || !Item.exists(entry.own)) return 'untouched';
      let foreign = entry.foreign.filter(item => accepts(entry.recipe, item));
      if (foreign.length === 0) return 'untouched';
      event.replaceInput({ id: entry.recipe }, entry.tag, entry.own);
      foreign.forEach(item => {
        if (accepts(entry.recipe, item)) throw 'still accepts ' + item;
      });
      if (!accepts(entry.recipe, entry.own)) throw 'no longer accepts ' + entry.own;
      return 'narrowed';
    };

    const run = (name, work, entry) => {
      try {
        report[work(entry)].push(name);
      } catch (failure) {
        report.failed.push(name + ' (' + failure + ')');
      }
    };
    SEPARATED.forEach(entry => { run(entry.move, separate, entry); });
    EXCLUDED.forEach(entry => { run(entry.recipe, exclude, entry); });
    OWN_ONLY.forEach(entry => { run(entry.recipe, restrict, entry); });
    console.info('PSA_RECIPE_COEXISTENCE ' + JSON.stringify(report));
  });
})();
