# -*- coding: utf-8 -*-
"""校验 installer/EULA.rtf：结构、括号平衡、中文 \\uN 转义可还原。"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.abspath(os.path.join(HERE, '..', 'installer', 'EULA.rtf'))


def main() -> None:
    data = open(P, 'r', encoding='ascii').read()
    assert data.startswith('{\\rtf1'), 'RTF header missing'
    assert data.rstrip().endswith('}'), 'RTF trailer missing'

    def decode(m: 're.Match[str]') -> str:
        return chr(int(m.group(1)) % 65536)

    text = re.sub(r'\\u(-?\d+)\?', decode, data)
    for kw in ('许可协议', '免责声明', '责任限制', '隐私', 'GPL', 'Wing North Studio'):
        assert kw in text, f'missing: {kw}'

    depth = 0
    i = 0
    while i < len(data):
        ch = data[i]
        if ch == '\\':
            i += 2
            continue
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
        assert depth >= 0, f'unbalanced "}}" at offset {i}'
        i += 1
    assert depth == 0, 'unbalanced braces at end'
    print(f'EULA.rtf OK: {len(text)} decoded chars, braces balanced')


if __name__ == '__main__':
    main()
