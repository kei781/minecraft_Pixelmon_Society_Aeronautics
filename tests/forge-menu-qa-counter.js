// Disposable QA only. Never export. Allocate at most 256 unspawned armor stands
// per tick to exercise real client menus with entity IDs above a short's range.
// Does not set the global counter, add entities, alter auth or change class filters.
var psaMenuCounterDone = false;
var psaMenuCounterAllocations = 0;
ServerEvents.tick(event => {
 if (psaMenuCounterDone) return;
 try {
  var psaRegistry = Java.loadClass('net.minecraftforge.registries.ForgeRegistries');
  var psaLocation = Java.loadClass('net.minecraft.resources.ResourceLocation');
  var psaArmorStand = psaRegistry.ENTITY_TYPES.getValue(new psaLocation('minecraft:armor_stand'));
  for (var psaIndex = 0; psaIndex < 256; psaIndex++) {
   var psaTemporary = psaArmorStand.create(event.server.overworld());
   var psaAllocatedId = psaTemporary.getId();
   psaTemporary.discard();
   psaMenuCounterAllocations++;
   if (psaAllocatedId >= 100000) {
    psaMenuCounterDone = true;
    console.info('PSA_MENU_QA_COUNTER_READY last_id=' + psaAllocatedId + ' allocations=' + psaMenuCounterAllocations);
    return;
   }
   if (psaMenuCounterAllocations >= 100001) throw new Error('Unexpected non-monotonic QA entity IDs');
  }
 } catch (error) {
  psaMenuCounterDone = true;
  console.error('PSA_MENU_QA_COUNTER_FAILED ' + error);
 }
});
