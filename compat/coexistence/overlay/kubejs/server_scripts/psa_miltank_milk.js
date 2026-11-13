// requires: pixelmon
//
// PSA Miltank milking under Society's milk rule (server side, KubeJS).
//
// Pixelmon lets a player milk a Miltank with an empty bucket and hands over a vanilla
// minecraft:milk_bucket. Society's playerEvents/milkBan.js allows no vanilla milk bucket in a
// player inventory and turns it straight back into an empty bucket, so the milking gave nothing.
// This script exchanges exactly that one bucket for one society:milk plus the empty bucket.
// Society's rule still holds (no vanilla milk bucket remains) and Society's file is not edited.
//
// How it stays exact:
// - The interaction is remembered only when Pixelmon is about to produce the bucket: main hand
//   holding minecraft:bucket, target a pixelmon:pixelmon entity of species Miltank with a milking
//   left, and the bucket not on cooldown. These are the conditions of Pixelmon 9.2.3
//   (PixelmonEntity.mobInteract, AbstractInteractionsEntity.mobInteract, MiltankInteraction).
// - One remembered interaction pays for one bucket, and only for WINDOW_TICKS game ticks. Pixelmon
//   puts the bucket into the inventory during the same interaction and KubeJS reports it on the
//   player's next tick, one game tick later. Any other vanilla milk bucket has no remembered
//   interaction and is left to Society's handler unchanged.
// - Order does not depend on file names: both handlers below are registered for one item id, and
//   KubeJS runs handlers registered for an item before the handlers registered without one, which
//   is how milkBan.js is registered.
// - The stack KubeJS passes with the inventory event is the menu's private copy of the slot. When
//   the exchanged bucket was the only vanilla milk bucket, that copy is emptied too, so Society's
//   handler finds nothing to confiscate and prints nothing. If another vanilla milk bucket is
//   present the copy is left alone and Society's handler removes that one as always.
// - KubeJS also posts this event for a crafted or smelted stack (slot -1), and that stack is the
//   real one, not a copy. It is never emptied here: only a stack reported with a menu slot is.
// - Nothing is given unless a vanilla milk bucket was really taken out of the inventory.
// - Every handler body is guarded: an error here must not stop Society's handlers for the event.
// - The header line is a KubeJS file property: the file is skipped when Pixelmon is not installed.
// - Rhino: `const` only at function top level; callbacks use `let`.
(() => {
  const BUCKET = 'minecraft:bucket';
  const MILK_BUCKET = 'minecraft:milk_bucket';
  const SOCIETY_MILK = 'society:milk';
  const MILTANK = 'Miltank';
  const WINDOW_TICKS = 2;
  // player uuid -> game time of the remembered interaction; emptied by use, expiry or reload.
  const remembered = {};
  const state = { warned: false };
  const warnOnce = (where, failure) => {
    if (state.warned) return;
    state.warned = true;
    console.warn('PSA_MILTANK_MILK ' + where + ' failed, vanilla milk stays under Society\'s rule: ' + failure);
  };

  const remember = event => {
    const player = event.player;
    const target = event.target;
    if ('' + event.hand !== 'MAIN_HAND') return;
    if ('' + target.type !== 'pixelmon:pixelmon') return;
    if (player.cooldowns.isOnCooldown(BUCKET)) return;
    if ('' + target.getSpecies().getName() !== MILTANK) return;
    if (!(target.getNumInteractions() > 0)) return;
    remembered['' + player.getUuid()] = event.level.getTime();
  };

  const exchange = event => {
    const player = event.player;
    const key = '' + player.getUuid();
    const since = remembered[key];
    if (since === undefined) return;
    delete remembered[key];
    const age = event.level.getTime() - since;
    if (!(age >= 0 && age <= WINDOW_TICKS)) return;
    const milk = Item.of(SOCIETY_MILK, 1);
    if ('' + milk.id !== SOCIETY_MILK) return;
    const found = { taken: false, others: 0 };
    player.inventory.items.forEach(stack => {
      if ('' + stack.id !== MILK_BUCKET) return;
      if (found.taken) {
        found.others++;
        return;
      }
      stack.count = stack.count - 1;
      found.taken = true;
      if ('' + stack.id === MILK_BUCKET) found.others++;
    });
    if (!found.taken) return;
    player.give(milk);
    player.give(Item.of(BUCKET, 1));
    if (found.others === 0 && event.slot >= 0 && '' + event.item.id === MILK_BUCKET) event.item.count = 0;
  };

  ItemEvents.entityInteracted(BUCKET, event => {
    try {
      remember(event);
    } catch (failure) {
      warnOnce('interaction check', failure);
    }
  });

  PlayerEvents.inventoryChanged(MILK_BUCKET, event => {
    try {
      exchange(event);
    } catch (failure) {
      warnOnce('exchange', failure);
    }
  });
})();
