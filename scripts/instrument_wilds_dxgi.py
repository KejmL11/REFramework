"""Instrument the known startup stall; desktop-first fallback is opt-in only."""
import argparse
from pathlib import Path
import re
import subprocess

REVISION = "d4611aef1d63effd3a736bdf9404ea702428017d"
FILE = "src/D3D12Hook.cpp"


def replace_once(text, pattern, replacement, label):
    result, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count != 1:
        raise ValueError(f"{label}: expected one source anchor, found {count}")
    return result


def transform(text):
    text = text.replace("\r\n", "\n")
    if "[Wilds startup]" in text:
        raise ValueError("Startup diagnostics already applied")
    if "#include <utility>" not in text:
        text = "#include <utility>\n" + text
    # Capture the original HWND descriptor. Reuse it for the opt-in early
    # desktop attempt, rather than inheriting the composition descriptor.
    descriptors = list(re.finditer(
        r"^[ \t]*swap_chain_desc1.BufferCount = 3;.*?^[ \t]*swap_chain_desc1.Stereo = FALSE;",
        text, re.MULTILINE | re.DOTALL,
    ))
    if len(descriptors) != 1:
        raise ValueError("Expected one original HWND swapchain descriptor")
    descriptor = descriptors[0].group(0)
    text = replace_once(text, r"^[ \t]*::RegisterClassEx\(&wc\);[ \t]*$", lambda m: '''        spdlog::info("[Wilds startup] RegisterClassEx begin (thread {})", GetCurrentThreadId());
        const auto class_atom = ::RegisterClassEx(&wc);
        const auto class_error = class_atom == 0 ? GetLastError() : ERROR_SUCCESS;
        spdlog::info("[Wilds startup] RegisterClassEx returned {}, error {}", class_atom, class_error);''', "Window registration")
    text = replace_once(text, r"^[ \t]*hwnd = ::CreateWindow\([^\n]+;[ \t]*$", lambda m: '''        spdlog::info("[Wilds startup] CreateWindow begin (thread {})", GetCurrentThreadId());
''' + m.group(0) + '''
        const auto window_error = hwnd == nullptr ? GetLastError() : ERROR_SUCCESS;
        spdlog::info("[Wilds startup] CreateWindow returned 0x{:x}, error {}", (uintptr_t)hwnd, window_error);''', "Dummy window creation")
    text = replace_once(text, r"^[ \t]*return !FAILED\(factory->CreateSwapChainForComposition\(command_queue, &swap_chain_desc1, nullptr, &swap_chain1\)\);[ \t]*$", lambda m: '''            spdlog::info("[Wilds startup] Composition swapchain begin");
            const auto hr = factory->CreateSwapChainForComposition(command_queue, &swap_chain_desc1, nullptr, &swap_chain1);
            spdlog::info("[Wilds startup] Composition swapchain returned 0x{:08x}", (unsigned long)hr);
            return SUCCEEDED(hr);''', "Composition swapchain")
    text = replace_once(text, r"^[ \t]*return !FAILED\(factory->CreateSwapChainForHwnd\(command_queue, hwnd, &swap_chain_desc1, nullptr, nullptr, &swap_chain1\)\);[ \t]*$", lambda m: '''            spdlog::info("[Wilds startup] Dummy HWND swapchain begin, hwnd 0x{:x}", (uintptr_t)hwnd);
            const auto hr = factory->CreateSwapChainForHwnd(command_queue, hwnd, &swap_chain_desc1, nullptr, nullptr, &swap_chain1);
            spdlog::info("[Wilds startup] Dummy HWND swapchain returned 0x{:08x}", (unsigned long)hr);
            return SUCCEEDED(hr);''', "Dummy HWND swapchain")
    text = replace_once(text, r"^[ \t]*return !FAILED\(factory->CreateSwapChainForHwnd\(command_queue, GetDesktopWindow\(\), &swap_chain_desc1, nullptr, nullptr, &swap_chain1\)\);[ \t]*$", lambda m: descriptor + '''
            spdlog::info("[Wilds startup] GetDesktopWindow begin");
            const auto desktop = GetDesktopWindow();
            spdlog::info("[Wilds startup] Desktop HWND swapchain begin, hwnd 0x{:x}", (uintptr_t)desktop);
            const auto hr = factory->CreateSwapChainForHwnd(command_queue, desktop, &swap_chain_desc1, nullptr, nullptr, &swap_chain1);
            spdlog::info("[Wilds startup] Desktop HWND swapchain returned 0x{:08x}", (unsigned long)hr);
            return SUCCEEDED(hr);''', "Desktop HWND swapchain")
    text = replace_once(text, r"^[ \t]*bool any_succeed = false;[ \t]*$", lambda m: '''    char desktop_first[2]{};
    const auto desktop_first_length = GetEnvironmentVariableA("REFRAMEWORK_MHWILDS_DESKTOP_FIRST", desktop_first, 2);
    const bool use_desktop_first = desktop_first_length == 1 && desktop_first[0] == '1';
    spdlog::info("[Wilds startup] DXGI diagnostics active; desktop-first fallback {}", use_desktop_first);
    if (use_desktop_first) {
        // Keep all original fallbacks; only change their order when requested.
        std::swap(swapchain_attempts[1], swapchain_attempts[2]);
    }

''' + m.group(0), "Optional fallback order")
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--diff", type=Path, required=True)
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True).strip()
    if revision != REVISION:
        raise ValueError("Unexpected upstream revision")
    dirty = subprocess.check_output(["git", "-C", str(args.source), "status", "--porcelain", "--", FILE], text=True)
    if dirty.strip():
        raise ValueError("D3D12 source already has changes")
    path = args.source / FILE
    changed = transform(path.read_text(encoding="utf-8"))
    with path.open("w", encoding="utf-8", newline="\n") as output:
        output.write(changed)
    subprocess.run(["git", "-C", str(args.source), "diff", "--check"], check=True)
    args.diff.write_bytes(subprocess.check_output(["git", "-C", str(args.source), "diff", "--", FILE]))
    print("Added DXGI stage logs and opt-in desktop-first fallback order")


if __name__ == "__main__":
    main()
