# Wilds early PAK diagnostic build

Pinned upstream: d4611aef1d63effd3a736bdf9404ea702428017d.

Retains the installed custom build's established early-integrity marker fix. Installs PAK hooks immediately afterward, before DLL staging. A public wrapper uses std::call_once to prevent duplicate installation by the later existing caller. This tests a startup timing hypothesis; it is not a confirmed fix. DXGI startup behavior is unchanged from pinned upstream; the separate experimental DXGI instrumentation is not applied.

Expected ordering: WildsPakEarly, successful PAK hook installation, then DLL staging. Success requires actual pak_load_patch_load_function callbacks and PAK injection, followed by the custom model in-game. A cached/listed PAK alone is insufficient.

The one-time guard does not retry a failed early scan; inspect scan failures in the log. Install only dinput8.dll with the game closed, retaining the prior DLL for rollback. Put the current mod in pak_mods/CaliScythe.pak; leave loose loading disabled.

Artifact: REFramework-01433-early-pak-diagnostics.
