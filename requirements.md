# Pixelmon + Society + Aeronautics

- Preserve all three requested projects in one playable Minecraft server and world.
- Work from real artifacts: download, inspect code/bytecode for likely conflicts, launch isolated profiles, diagnose failures, fix, and rerun. The user suggested investigating `npx rea-agents setup` if direct analysis is insufficient; upstream replies are not a prerequisite for independent work.
- Pixelmon is the official project linked from https://reforged.gg/ko; the earlier DigiDatapack is no longer requested.
- Server target: Intel N100, Ubuntu, 16 GB physical RAM, up to six concurrent players.
- Windows players need a repeatable way to install the matching client. Instructions to install prerequisites such as a launcher/Java and then import the prepared modpack are acceptable; a single self-contained executable or fully unattended setup is not required. Each player signs in with their own Microsoft account.
- Do not silently substitute Digimobs, Cobblemon, Eureka, or a generic farming pack.
- Society's published pack uses Minecraft 1.20.1 Forge. Its official `project-honey` development branch uses Minecraft 1.21.1 NeoForge, and is an experimental integration candidate, not the published 4.1.5 release or a proven full equivalent.
- Preserve the original Society 1.21.1 baseline at commit 5e7c8fa9073a86f9ac74c7cbf087551e5872016c and its missing-file gates. A separate, explicitly labelled 1.20.1 candidate may use the published Society release and real Aeronautics Forge port; the user has not required a Minecraft version. Pin each candidate's actual sources, artifacts and modifications, and validate its features. Do not present an unofficial port or older Pixelmon beta as the current official releases.
- Verify official input files against their distribution metadata's published hashes and sizes. Retain the official URLs and upstream hashes alongside locally computed derived-build hashes.
- Public unmodified Orchard and Plentiful Ponds source builds are allowed as experimental candidates. Pin their source commits and binary SHA256, retain the original developer SHA1 separately, and do not claim identical binaries or verified gameplay. Missing Society and Sunrise Gardening must still stop staging.
- Include the pinned Fancy Tab Sections and LibTooltips on the server: the Ponds build embeds older copies, and an actual partial-pack load reproduced NoSuchMethodError until the newer top-level jars were supplied.
- Preserve Society's vanilla mob progression alongside Pixelmon. Pixelmon 9.4.1's allow-vanilla-mobs flag only restores the world spawning rule; its separate entity-join replacements must also be neutralized. Keep the independent Pixelmon spawners and entity insertion available. Test with config-only and data-override controls.
- Start by proving the actual development snapshot can load with Pixelmon, Aeronautics, Sable, and the Society configuration. Failed launches and missing upstream artifacts must remain visible and must not be reported as working integration.
- Do not deploy to an existing server or overwrite worlds during local preparation.

Acceptance requires successful startup with all required content; a documented Windows installation path (guide and/or script) and a Windows client connecting; Pixelmon capture/battle; Society farming/economy/progression; Aeronautics vehicle assembly and flight; and actual six-player load measurements on the N100. None of these is presumed complete from matching version numbers.
