"""Move the existing integrity marker patch earlier in pinned Nightly 01433.

Extract the marker loop from the real Git checkout, preserving its code and
patch ownership. Refuse ambiguous anchors and write nothing until validated.
"""
import argparse
from pathlib import Path
import re
import subprocess

REVISION = "d4611aef1d63effd3a736bdf9404ea702428017d"
STARTUP = "src/REFramework.cpp"
IMPLEMENTATION = "src/mods/IntegrityCheckBypass.cpp"
HEADER = "src/mods/IntegrityCheckBypass.hpp"
FILES = (STARTUP, IMPLEMENTATION, HEADER)


def unique(pattern, text, label):
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if len(matches) != 1:
        raise ValueError(f"{label}: expected one anchor, found {len(matches)}")
    return matches[0]


def transform(originals):
    files = {name: text.replace("\r\n", "\n") for name, text in originals.items()}
    if any("patch_dd2_check_constants" in text for text in files.values()):
        raise ValueError("Early marker helper already exists; refusing duplicate application")
    cpp = files[IMPLEMENTATION]
    entry = unique(r"^void IntegrityCheckBypass::immediate_patch_dd2\(\)\s*\{", cpp, "DD2 initializer")
    close = cpp.find("\n}", entry.end())
    if close < 0:
        raise ValueError("DD2 initializer closing brace not found")
    body = cpp[entry.end():close]
    begin = unique(r"^[ \t]*static std::vector<Patch::Ptr> sus_constant_patches\{\};[ \t]*$", body, "Marker patch owner")
    end = unique(r'^[ \t]*spdlog::info\("\[IntegrityCheckBypass\]: Patched \{\} sus_constants! \(DD2\+ variant\)", sus_constant_patches.size\(\)\);[ \t]*$', body, "Marker patch log")
    if end.start() <= begin.end():
        raise ValueError("Marker block anchors are out of order")
    block = body[begin.start():end.end()]
    if block.count('"81 ? E1 53 BD 4C"') != 2 or block.count("sus_constant_patches.emplace_back") != 1:
        raise ValueError("Unexpected marker loop; no changes written")
    if "{ 0xEF, 0xBE, 0x37, 0x13 }" not in block:
        raise ValueError("Unexpected marker replacement bytes; no changes written")
    size = unique(r"^[ \t]*const auto game_size = utility::get_module_size\(game\).value_or\(0\);[ \t]*$", body, "Game scan size")
    bound = unique(r"^[ \t]*const auto game_end = \(uintptr_t\)game \+ game_size;[ \t]*\n", body, "Game scan bound")
    helper = (
        "void IntegrityCheckBypass::patch_dd2_check_constants() {\n"
        "    const auto game = utility::get_executable();\n"
        "    const auto game_size = utility::get_module_size(game).value_or(0);\n"
        "    const auto game_end = (uintptr_t)game + game_size;\n"
        + block + "\n}\n\n"
    )
    body = body[:begin.start()] + "    patch_dd2_check_constants();" + body[end.end():]
    # Remove the bound only if the moved loop was its sole consumer.
    bound = unique(r"^[ \t]*const auto game_end = \(uintptr_t\)game \+ game_size;[ \t]*\n", body, "Remaining game scan bound")
    without_bound = body[:bound.start()] + body[bound.end():]
    if not re.search(r"\bgame_end\b", without_bound):
        body = without_bound
    files[IMPLEMENTATION] = cpp[:entry.start()] + helper + cpp[entry.start():entry.end()] + body + cpp[close:]

    startup = files[STARTUP]
    call = unique(r"^[ \t]*IntegrityCheckBypass::fix_virtual_protect\(\);[ \t]*$", startup, "Early startup hook")
    early = (
        "\n\n    // Wilds checks can run while DLL copying delays initialization.\n"
        "    // Apply the existing markers before that filesystem work.\n"
        "    if (gi.is_mhwilds()) {\n"
        "        IntegrityCheckBypass::patch_dd2_check_constants();\n"
        "    }"
    )
    files[STARTUP] = startup[:call.end()] + early + startup[call.end():]
    header = files[HEADER]
    declaration = unique(r"^[ \t]*static void immediate_patch_dd2\(\);[ \t]*$", header, "Public helper declaration")
    files[HEADER] = header[:declaration.end()] + "\n    static void patch_dd2_check_constants();" + header[declaration.end():]
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--diff", type=Path, required=True)
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "-C", str(args.source), "rev-parse", "HEAD"], text=True).strip()
    print("Actual upstream revision:", revision, flush=True)
    if revision != REVISION:
        raise ValueError("Upstream revision differs from pinned Nightly 01433")
    dirty = subprocess.check_output(["git", "-C", str(args.source), "status", "--porcelain", "--", *FILES], text=True)
    if dirty.strip():
        raise ValueError("Target source files already have changes")
    originals = {name: (args.source / name).read_text(encoding="utf-8") for name in FILES}
    changed = transform(originals)
    for name in FILES:
        with (args.source / name).open("w", encoding="utf-8", newline="\n") as output:
            output.write(changed[name])
    subprocess.run(["git", "-C", str(args.source), "diff", "--check"], check=True)
    diff = subprocess.check_output(["git", "-C", str(args.source), "diff", "--", *FILES])
    args.diff.write_bytes(diff)
    print("Moved existing marker loop into shared helper and installed early Wilds call.")
    print("Reviewable diff:", args.diff)
    subprocess.run(["git", "-C", str(args.source), "diff", "--stat"], check=True)


if __name__ == "__main__":
    main()
