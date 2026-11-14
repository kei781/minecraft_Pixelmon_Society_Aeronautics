// Test-only. Runs Pixelmon's own login handler for a server-side stand-in player, without posting
// the login event, so nothing but the PC resend class asks for that player's PC. The class
// writes one debug line per resend; the driver reads it from logs/debug.log.
// Never part of a player or production profile.
(function () {
  ServerEvents.commandRegistry(event => {
    const { commands: Commands } = event;
    event.register(Commands.literal('psa_probe_pc_resend').requires(source => source.hasPermission(4))
      .executes(context => {
        const result = { name: 'PSA_PC_Probe', handler_completed: false, error: null };
        try {
          let JavaUuid = Java.loadClass('java.util.UUID');
          let GameProfile = Java.loadClass('com.mojang.authlib.GameProfile');
          let FakePlayerFactory = Java.loadClass('net.minecraftforge.common.util.FakePlayerFactory');
          let LoggedIn = Java.loadClass('net.minecraftforge.event.entity.player.PlayerEvent$PlayerLoggedInEvent');
          let Tracker = Java.loadClass('com.pixelmonmod.pixelmon.listener.PixelmonPlayerTracker');
          let level = context.source.server.overworld();
          let player = FakePlayerFactory.get(level, new GameProfile(JavaUuid.fromString('0b5a1c5e-7f3d-4c2a-9a41-5053415f5043'), result.name));
          Tracker.onPlayerLogin(new LoggedIn(player));
          result.handler_completed = true;
        } catch (error) {
          result.error = String(error);
        }
        console.info('PSA_PROBE_PC_RESEND ' + JSON.stringify(result));
        return 1;
      }));
  });
})();
