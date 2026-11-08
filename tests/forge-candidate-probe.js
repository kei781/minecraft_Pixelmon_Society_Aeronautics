// Isolated server test only. Do not include this in the player/server release.
ServerEvents.loaded(event => {
  const source = event.server.createCommandSourceStack();
  const node = event.server.getCommands().getDispatcher().getRoot().getChild('sable');
  if (node === null) throw new Error('PSA: Sable command was not registered');
  const ordinaryDenied = !node.canUse(source.withPermission(0));
  const operatorAllowed = node.canUse(source.withPermission(2));
  console.info('PSA_SABLE_COMMAND_PERMISSIONS ordinaryDenied=' + ordinaryDenied + ' operatorAllowed=' + operatorAllowed);
  if (!ordinaryDenied || !operatorAllowed) throw new Error('PSA: unsafe Sable command permissions');
});
