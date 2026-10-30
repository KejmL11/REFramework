"""Install Wilds PAK hooks before DLL staging; retain the existing startup fix."""
import argparse
from pathlib import Path
import subprocess

FILES = ('src/REFramework.cpp', 'src/mods/IntegrityCheckBypass.cpp', 'src/mods/IntegrityCheckBypass.hpp')


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Expected unique source anchor: ' + old)
    return text.replace(old, new, 1)


def transform(originals):
    changed = dict(originals)
    startup, cpp, header = (changed[name] for name in FILES)
    if 'WildsPakEarly' in startup or 'restore_unencrypted_paks_impl' in cpp:
        raise ValueError('PAK patch already applied')
    startup = replace_once(startup,
        '        IntegrityCheckBypass::patch_dd2_check_constants();',
        '        IntegrityCheckBypass::patch_dd2_check_constants();\n'
        '        spdlog::info("[WildsPakEarly]: Installing PAK hooks before DLL staging");\n'
        '        IntegrityCheckBypass::restore_unencrypted_paks();')
    cpp = replace_once(cpp, '#include <unordered_map>', '#include <unordered_map>\n#include <mutex>')
    cpp = replace_once(cpp, 'void IntegrityCheckBypass::restore_unencrypted_paks() {',
        'void IntegrityCheckBypass::restore_unencrypted_paks() {\n'
        '    static std::once_flag install_once;\n'
        '    std::call_once(install_once, []() { restore_unencrypted_paks_impl(); });\n'
        '}\n\n'
        'void IntegrityCheckBypass::restore_unencrypted_paks_impl() {')
    header = replace_once(header, '    static void restore_unencrypted_paks();',
        '    static void restore_unencrypted_paks_impl();')
    header = replace_once(header, '    static void patch_dd2_check_constants();',
        '    static void patch_dd2_check_constants();\n'
        '    static void restore_unencrypted_paks();')
    if header.index('    static void restore_unencrypted_paks();') > header.index('private:'):
        raise ValueError('Early PAK entry point is not public')
    if startup.index('IntegrityCheckBypass::restore_unencrypted_paks();') > startup.index('Copying DLL file:'):
        raise ValueError('PAK initialization did not precede DLL staging')
    return dict(zip(FILES, (startup, cpp, header)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--diff', type=Path, required=True)
    args = parser.parse_args()
    originals = {name: (args.source/name).read_text(encoding='utf-8') for name in FILES}
    changed = transform(originals)
    import difflib
    patch = ''.join(''.join(difflib.unified_diff(originals[name].splitlines(True), changed[name].splitlines(True), fromfile='a/'+name, tofile='b/'+name)) for name in FILES)
    for name in FILES:
        (args.source/name).write_text(changed[name], encoding='utf-8', newline='\n')
    args.diff.write_text(patch, encoding='utf-8')
    subprocess.run(['git', '-C', str(args.source), 'diff', '--check'], check=True)
    print('Installed Wilds PAK hooks before DLL staging with one-time initialization.')


if __name__ == '__main__':
    main()
