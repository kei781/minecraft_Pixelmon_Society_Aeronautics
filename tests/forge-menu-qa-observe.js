// Read only, disposable QA only; remove after recording tagged fixture IDs.
var psaMenuObserveDone = false;
ServerEvents.tick(event => {
 if (psaMenuObserveDone) return;
 psaMenuObserveDone = true;
 try {
  var psaMenuEntities = event.server.overworld().getAllEntities().iterator();
  var psaMenuRows = [];
  while (psaMenuEntities.hasNext()) {
   var psaMenuEntity = psaMenuEntities.next();
   if (!psaMenuEntity.getTags().contains('psa_menu_high_id')) continue;
   var psaMenuRow = {type: String(psaMenuEntity.type), runtime_id: psaMenuEntity.getId()};
   if (psaMenuRow.type === 'moreminecarts:tank_cart') psaMenuRow.fluid_mb = psaMenuEntity.getFluidStack().getAmount();
   if (psaMenuRow.type === 'moreminecarts:battery_cart') psaMenuRow.energy_fe = psaMenuEntity.getEnergyAmount();
   psaMenuRows.push(psaMenuRow);
  }
  console.info('PSA_MENU_QA_OBSERVE ' + JSON.stringify(psaMenuRows));
 } catch (error) { console.error('PSA_MENU_QA_OBSERVE_FAILED ' + error); }
});
