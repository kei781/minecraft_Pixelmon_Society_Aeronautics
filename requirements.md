# Pixelmon + Society + Aeronautics

- Preserve all three requested projects in one playable Minecraft server and world.
- Pixelmon is the official project linked from https://reforged.gg/ko; the earlier DigiDatapack is no longer requested.
- Server target: Intel N100, Ubuntu, 16 GB physical RAM, up to six concurrent players.
- Windows players need a double-click installer that prepares the matching client, without manually selecting or copying individual mods. Each player signs in with their own Microsoft account.
- Do not silently substitute Digimobs, Cobblemon, Eureka, or a generic farming pack.
- Society's published pack uses Minecraft 1.20.1 Forge. Its official `project-honey` development branch uses Minecraft 1.21.1 NeoForge, and is an experimental integration candidate, not the published 4.1.5 release or a proven full equivalent.
- Freeze Society at commit 5e7c8fa9073a86f9ac74c7cbf087551e5872016c. Freeze every downloaded binary and verify its upstream hash.
- Public unmodified Orchard and Plentiful Ponds source builds are allowed as experimental candidates. Pin their source commits and binary SHA256, retain the original developer SHA1 separately, and do not claim identical binaries or verified gameplay. Missing Society and Sunrise Gardening must still stop staging.
- Include the pinned Fancy Tab Sections and LibTooltips on the server: the Ponds build embeds older copies, and an actual partial-pack load reproduced NoSuchMethodError until the newer top-level jars were supplied.
- Start by proving the actual development snapshot can load with Pixelmon, Aeronautics, Sable, and the Society configuration. Failed launches and missing upstream artifacts must remain visible and must not be reported as working integration.
- Do not deploy to an existing server or overwrite worlds during local preparation.

Acceptance requires successful startup with all required content; a Windows client connecting; Pixelmon capture/battle; Society farming/economy/progression; Aeronautics vehicle assembly and flight; and actual six-player load measurements on the N100. None of these is presumed complete from matching version numbers.
