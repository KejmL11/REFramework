# MH Wilds early PAK hook diagnostic

Status: source patch prepared; not compiled or installed; not a confirmed fix.

Base: official d4611aef1d63effd3a736bdf9404ea702428017d plus the existing local early-integrity transformation. The installed DLL is a custom build, despite sharing the official commit label.

Observed on 2026-10-30: the five integrity markers are patched before DLL staging; PAK hooks are installed roughly 13 seconds later; no PAK-loading callback or archive injection is subsequently logged. The current model, MDF, and four TEX entries in the generated archive match their source files. Both numbered-patch tests left the original model visible. Open-file inspection did not return either official or custom archive handles, so it provided no evidence about mounting.

Hypothesis: archive mounting runs before the PAK hooks become active. It remains possible that another compatibility or packaging problem is involved.

Changes:
- Retain the existing early integrity-marker fix.
- On MH Wilds only, call restore_unencrypted_paks immediately after that fix and before DLL staging.
- Make that helper callable from REFramework's constructor.
- Use std::call_once so the later existing initialization does not reinstall hooks.
- Add the WildsPakEarly log marker for ordering verification.

Validation performed: fetched the exact pinned upstream files; applied the checked original startup transformation; checked declaration visibility and ordering; verified the one-time guard. No Windows compilation or in-game validation has occurred. A failed early pattern scan is not retried by this diagnostic's once guard; inspect its log before interpreting the test.

Build requires the Windows/MSVC workflow. The existing user-owned build workflow is in KejmL11/REFramework, wilds-01433-early-fix.yml. Publishing changes and starting CI require user approval. Preserve any unrelated current startup diagnostics.

Test only after successful compilation: back up the active DLL, install only the new dinput8.dll with the game closed, return the current mod to pak_mods/CaliScythe.pak, and leave loose loading disabled. Confirm WildsPakEarly and successful PAK hook logs precede DLL staging, then look for actual PAK-loading callbacks and injection. Retain the old DLL for immediate rollback if startup regresses.
