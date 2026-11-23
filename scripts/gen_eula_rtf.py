# -*- coding: utf-8 -*-
"""生成 Inno Setup 用的 EULA.rtf（中文按 RTF \\uN 转义）。"""
import os


def esc(text: str) -> str:
    out = []
    for ch in text:
        code = ord(ch)
        if ch in ('\\', '{', '}'):
            out.append('\\' + ch)
        elif ch == '\n':
            out.append('\\line ')
        elif code > 127:
            n = code if code < 32768 else code - 65536
            out.append('\\u%d?' % n)
        else:
            out.append(ch)
    return ''.join(out)


PARAS = [
    ("软件最终用户许可协议（EULA）", True),
    ("Catagorize for Windows 版本 0.1.8\n"
     "版权所有 © 2026 Wing North Studio。保留所有权利。", False),
    ("重要提示：在安装或使用本软件之前，请仔细阅读本协议。"
     "点击「我同意」或安装、使用本软件，即表示您已阅读、理解并接受本协议的全部条款。"
     "如果您不同意本协议的任何条款，请勿安装或使用本软件，并请删除本软件的全部副本。", False),
    ("1. 许可的授予\n"
     "在遵守本协议条款的前提下，版权方授予您一项非排他性、不可转让、不可再许可的许可，"
     "允许您在任意数量的属于您本人或由您管理的计算机上安装和使用本软件的可执行版本，"
     "仅用于个人或非商业用途。商业性分发、出租、出借、再许可或以任何方式向第三方提供本软件，"
     "均需事先获得版权方的书面同意。", False),
    ("2. 软件的提供与更新\n"
     "本软件按「现状」提供。版权方可能通过内置的更新检查功能提示新版本；"
     "更新检查仅访问公开的版本发布信息，不收集任何个人数据。"
     "是否下载和安装更新完全由您自行决定。", False),
    ("3. 禁止的行为\n"
     "您不得：(a) 对本软件进行反向工程、反编译或反汇编，但适用法律明确禁止此类限制的除外；"
     "(b) 删除或修改本软件中的任何版权声明或其他权利声明；"
     "(c) 将本软件用于任何违反适用法律法规的目的。", False),
    ("4. 数据与隐私\n"
     "本软件的所有索引、配置、日志与操作记录均存储在您的本机用户配置目录"
     "（或便携模式下的程序目录）中，全部数据处理均在本地完成。"
     "本软件不包含任何遥测、追踪或联网上传用户数据的功能。"
     "版权方不接触、不存储、也无法访问您的任何文件数据。", False),
    ("5. 用户文件\n"
     "本软件对受管目录中的文件执行的唯一动作是「移动」。"
     "本软件的设计目标是在任何时候都不删除用户文件；"
     "但因不可抗力、系统故障或用户误操作导致的数据损失，版权方不承担责任。"
     "建议您在使用整理功能前备份重要数据。", False),
    ("6. 免责声明\n"
     "在适用法律允许的最大范围内，版权方不对本软件作出任何明示或默示的保证，"
     "包括但不限于对适销性、特定用途适用性及不侵权的默示保证。"
     "版权方不保证本软件无错误或运行不中断。使用本软件所产生的全部风险由您自行承担。", False),
    ("7. 责任限制\n"
     "在适用法律允许的最大范围内，对于因使用或无法使用本软件而产生的任何直接、间接、附带、"
     "特殊、惩罚性或后果性损害（包括但不限于数据丢失、利润损失或业务中断），"
     "无论基于何种责任理论，版权方均不承担任何责任，"
     "即使版权方已被告知此类损害的可能性。", False),
    ("8. 第三方组件\n"
     "本软件基于 PySide6（LGPL v3 / GPL v3）、PySide6-Fluent-Widgets（GPL-3.0）"
     "等开源组件构建，各自的许可证文本随其官方发行渠道提供。"
     "这些组件的许可证条款适用于相应组件本身。", False),
    ("9. 协议的终止\n"
     "如果您违反本协议的任何条款，本协议及您获得的许可将自动终止。"
     "终止后，您必须立即删除本软件的全部副本。", False),
    ("10. 适用法律\n"
     "本协议受中华人民共和国法律管辖，并按其解释，法律冲突规则除外。", False),
    ("11. 其他\n"
     "如果您对本协议有任何疑问，请通过软件「设置 → 关于」页面中列出的项目仓库与我们联系。", False),
]


def build_rtf() -> str:
    body = []
    for text, is_title in PARAS:
        if is_title:
            body.append('\\pard\\qc\\fs36\\b ' + esc(text) + '\\b0\\fs24\\par')
            continue
        lines = text.split('\n')
        body.append('\\pard\\sa120\\fi0 ' + esc(lines[0]) + '\\par')
        for ln in lines[1:]:
            body.append('\\pard\\sa120 ' + esc(ln) + '\\par')
    return (
        '{\\rtf1\\ansi\\deff0\n'
        '{\\fonttbl{\\f0 Microsoft YaHei;}{\\f1 SimSun;}}\n'
        '\\viewkind4\\uc1\\fs24\n'
        + '\n'.join(body) +
        '\n}'
    )


if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, '..', 'installer', 'EULA.rtf')
    path = os.path.abspath(path)
    data = build_rtf().replace('\n', '\r\n')
    with open(path, 'w', encoding='ascii', newline='') as f:
        f.write(data)
    print('written:', path, os.path.getsize(path), 'bytes')
