# Wilds 01433 startup diagnostic build

This workflow builds the pinned official 01433 source with the established early-integrity fix plus targeted DXGI startup instrumentation. It is a test build, not a confirmed compatibility fix for the new game version.

Download the **REFramework-01433-startup-diagnostics** artifact. With the game closed, back up the installed DLL and replace only `dinput8.dll` with the DLL inside the ZIP. Preserve the scripts and their settings.

First launch with existing Steam options unchanged. The log now shows begin/return messages for window registration, helper-window creation, composition swapchain creation, helper-window swapchain creation, and desktop-window swapchain creation. Failed DXGI calls include the HRESULT. The last unmatched `begin` message narrows down the stall.

For a second test, add `REFRAMEWORK_MHWILDS_DESKTOP_FIRST=1` before the existing Steam launch command. This changes the swapchain attempt order from composition → helper window → desktop window to composition → desktop window → helper window. All original fallbacks remain available, and desktop attempts use the original HWND descriptor settings. Without that variable, the order stays unchanged.

For example, if the only existing launch option is the standard REFramework override, the second test is:

```sh
REFRAMEWORK_MHWILDS_DESKTOP_FIRST=1 WINEDLLOVERRIDES="dinput8.dll=n,b" %command%
```

The log reports whether desktop-first mode is active. Reordering attempts may avoid a hang in helper-window creation if the desktop attempt succeeds. If it fails, the helper-window fallback is still tried and may hang again. The diagnostic logs distinguish these cases; this is not a timeout or a guarantee against hangs.

Neither the SDK signature scans nor renderer-layout definitions are changed in this build. Existing lookup errors may have functioning fallbacks; they should not be patched merely because they appear in the log. The latest observed startup stall was inside swapchain attempt 1, after the early integrity patches were already installed.

Remove the environment variable and restore the backed-up DLL to undo the experiment. CI uploads both applied source diffs for review.
