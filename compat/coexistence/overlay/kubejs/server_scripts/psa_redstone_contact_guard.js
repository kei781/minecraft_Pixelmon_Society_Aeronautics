// PSA temporary guard for Create's Redstone Contact (server side, KubeJS).
//
// In this pack a placed create:redstone_contact stops the server, and the saved block stops it again
// every time its chunk loads. The Aeronautics port gives the block a block entity with
// dev.ryanhcode.sable.forge.mixin.compatibility.create.redstone_contacts.RedstoneContactBlockMixin;
// its getTicker calls IBE.super.getTicker, which the pack's Mixin version rebinds to the block class
// itself, and the JVM rejects that call (IncompatibleClassChangeError) the first time the server asks
// for the ticker. The repair is a change to the port's source and needs a rebuilt mod JAR.
//
// Until that JAR is in place this script keeps the block out of the world:
// - the crafting recipes that make the item are removed, so in survival neither a player nor a
//   deployer or schematicannon has one to place;
// - using the item on a block is refused, for players and for Create deployers (both raise the
//   same right-click event).
// Not covered: /setblock, /fill and /clone by operators, and contacts placed earlier. Create elevator
// floors need this block and are unavailable meanwhile.
//
// Remove this file, and its checks in tests/forge-coexistence-checks.json, with the repaired JAR.
//
// Rhino: `const` only at function top level; callbacks use `let`.
(() => {
  const ITEM = 'create:redstone_contact';
  const NOTICE = '레드스톤 접점은 설치하면 서버가 멈추는 오류가 있어 임시로 막았습니다. '
    + '(Redstone Contact is disabled for now: placing it stops the server.)';

  ServerEvents.recipes(event => {
    const before = event.countRecipes({ output: ITEM });
    event.remove({ output: ITEM });
    console.info('PSA_REDSTONE_CONTACT_GUARD ' + JSON.stringify({ item: ITEM, recipes_removed: before }));
  });

  BlockEvents.rightClicked(event => {
    if ('' + event.item.id !== ITEM) return;
    try {
      if (!event.player.isFake()) event.player.tell(Text.of(NOTICE).red());
    } catch (failure) {
      // The refusal below matters; the chat line does not.
    }
    event.cancel();
  });
})();
