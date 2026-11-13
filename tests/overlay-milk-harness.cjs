// Runs compat/coexistence/overlay/.../psa_miltank_milk.js against stand-ins for the KubeJS bindings,
// Pixelmon's milking (MiltankInteraction + DropItemHelper.giveItemStack) and Society's milkBan.js.
// Logic only: no Minecraft, Forge, KubeJS or Rhino class is loaded.
// usage: node overlay-milk-harness.cjs <script>   -> JSON of scenario results on stdout
const fs = require('fs')
const vm = require('vm')

const LIMIT = { 'minecraft:bucket': 16, 'minecraft:milk_bucket': 1 }
class Stack {
    constructor(id, count) { this.item = id; this.count = count }
    get id() { return this.count > 0 ? this.item : 'minecraft:air' }
}
const handlers = { interacted: {}, inventory: {}, dropped: {} }
const warnings = []
const level = { time: 100, getTime() { return this.time } }
const sandbox = {
    console: { warn: text => warnings.push(text), info() {} },
    Item: { of: (id, count) => new Stack(id, count === undefined ? 1 : count) },
    ItemEvents: {
        entityInteracted: (id, handler) => { handlers.interacted[id] = handler },
        dropped: (id, handler) => { handlers.dropped[id] = handler },
    },
    PlayerEvents: { inventoryChanged: (id, handler) => { handlers.inventory[id] = handler } },
}
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), sandbox)

class Player {
    constructor(uuid, slots) {
        this.uuid = uuid
        this.inventory = { items: Array.from({ length: slots }, () => new Stack('minecraft:air', 0)) }
        this.cooling = {}
        this.cooldowns = { isOnCooldown: id => this.cooling[id] === true }
        this.ground = []
        this.messages = 0
    }
    getUuid() { return this.uuid }
    add(stack) {  // Inventory.add: merge, then a free slot; false when nothing fits
        const items = this.inventory.items
        const same = items.find(slot => slot.id === stack.id && slot.count < (LIMIT[stack.id] || 64))
        if (same) { same.count += stack.count; return true }
        const free = items.findIndex(slot => slot.count <= 0)
        if (free < 0) return false
        items[free] = new Stack(stack.id, stack.count)
        return true
    }
    give(stack) { if (!this.add(stack)) this.ground.push(stack) }
    contents() {
        const totals = {}
        for (const slot of this.inventory.items) if (slot.count > 0) totals[slot.id] = (totals[slot.id] || 0) + slot.count
        return totals
    }
}
const miltank = milkings => ({ type: 'pixelmon:pixelmon', milkings, getSpecies: () => ({ getName: () => 'Miltank' }), getNumInteractions() { return this.milkings } })

// Pixelmon 9.2.3: the bucket in the main hand is taken; the milk bucket replaces a last bucket,
// otherwise it is added to the inventory or, when nothing fits, dropped through Player.drop.
function milk(player, target, slot) {
    const held = player.inventory.items[slot]
    const handler = handlers.interacted[held.id]
    if (handler) handler({ player, target, hand: 'MAIN_HAND', item: held, level })
    if (!target.getSpecies || target.getSpecies().getName() !== 'Miltank' || target.milkings <= 0 || held.id !== 'minecraft:bucket') return
    held.count -= 1
    const produced = new Stack('minecraft:milk_bucket', 1)
    if (held.count <= 0) {
        player.inventory.items[slot] = produced
    } else if (!player.add(produced)) {
        const entity = { stack: produced, getItem() { return this.stack }, setItem(stack) { this.stack = stack } }
        const dropped = handlers.dropped[produced.id]
        if (dropped) dropped({ player, itemEntity: entity, item: entity.stack, level })
        player.ground.push(entity.stack)
    }
    target.milkings -= 1
}
// One player tick: KubeJS reports each vanilla milk bucket slot with the menu's copy of the stack;
// then Society's rule turns any vanilla milk bucket still present into an empty bucket.
function tick(player) {
    level.time += 1
    player.inventory.items.forEach((slot, index) => {
        if (slot.id !== 'minecraft:milk_bucket') return
        const copy = new Stack(slot.item, slot.count)
        const handler = handlers.inventory[copy.id]
        if (handler) handler({ player, item: copy, slot: index, level })
    })
    for (const slot of player.inventory.items) {
        if (slot.id !== 'minecraft:milk_bucket') continue
        slot.count = 0
        player.give(new Stack('minecraft:bucket', 1))
        player.messages += 1
    }
}
function filled(player, from) {
    for (let index = from; index < player.inventory.items.length; index++) player.inventory.items[index] = new Stack('minecraft:cobblestone', 64)
}
const report = player => ({ inventory: player.contents(), ground: player.ground.map(stack => stack.id + ' x' + stack.count), society_refusals: player.messages })

const results = {}
{   // the last bucket becomes the milk bucket in the hand slot
    const player = new Player('a', 4)
    player.inventory.items[0] = new Stack('minecraft:bucket', 1)
    milk(player, miltank(2), 0); tick(player); tick(player)
    results.single_bucket = report(player)
}
{   // a stack of buckets and a free slot: the milk bucket lands in the inventory
    const player = new Player('b', 4)
    player.inventory.items[0] = new Stack('minecraft:bucket', 3)
    milk(player, miltank(2), 0); tick(player); tick(player)
    results.stack_with_room = report(player)
}
{   // a stack of buckets and no free slot: Pixelmon drops the milk bucket; picked up much later
    const player = new Player('c', 4)
    player.inventory.items[0] = new Stack('minecraft:bucket', 3)
    filled(player, 1)
    milk(player, miltank(2), 0)
    for (let index = 0; index < 40; index++) tick(player)
    results.stack_with_full_inventory = report(player)
}
{   // a vanilla milk bucket that no milking produced stays under Society's rule
    const player = new Player('d', 4)
    player.give(new Stack('minecraft:milk_bucket', 1)); tick(player)
    results.foreign_milk_bucket = report(player)
}
{   // a milk bucket dropped without a remembered milking is not touched
    const player = new Player('e', 4)
    const entity = { stack: new Stack('minecraft:milk_bucket', 1), getItem() { return this.stack }, setItem(stack) { this.stack = stack } }
    handlers.dropped['minecraft:milk_bucket']({ player, itemEntity: entity, item: entity.stack, level })
    results.unrelated_drop = { dropped: entity.stack.id, inventory: player.contents() }
}
{   // the remembered milking pays once: a later foreign bucket is refused as always
    const player = new Player('f', 4)
    player.inventory.items[0] = new Stack('minecraft:bucket', 3)
    filled(player, 1)
    milk(player, miltank(2), 0); tick(player)
    player.inventory.items[1] = new Stack('minecraft:milk_bucket', 1); tick(player)
    results.dropped_then_foreign_bucket = report(player)
}
results.warnings = warnings
console.log(JSON.stringify(results))
