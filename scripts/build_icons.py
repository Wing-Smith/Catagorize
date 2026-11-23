# -*- coding: utf-8 -*-
"""从 Images/Catagorize.png 生成全套图标资源。

产物（写入 app/assets/）：
- app.ico        多尺寸 ICO（16/24/32/48/64/128/256），exe / 窗口 / 安装程序用
- icon.png       256x256，通知、关于区、头像用
- icon_shadow.png 带投影版本，启动画面用（原注释约定投影预烘焙进 PNG）
"""
import os

from PIL import Image, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, '..', 'Images', 'Catagorize.png'))
OUT = os.path.abspath(os.path.join(HERE, '..', 'app', 'assets'))

ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def build_ico(src: Image.Image) -> None:
    ico_path = os.path.join(OUT, 'app.ico')
    # ICO 要求恰好 256 的源；Pillow 会从传入列表生成各尺寸
    src.resize((256, 256), Image.LANCZOS).save(
        ico_path, format='ICO', sizes=[(s, s) for s in ICO_SIZES]
    )
    print('app.ico:', ICO_SIZES)


def build_png(src: Image.Image) -> None:
    src.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, 'icon.png'))
    print('icon.png: 256x256')


def build_shadow(src: Image.Image) -> None:
    """把图标放到加大画布上，下方烘焙柔和投影。"""
    pad_ratio = 0.10          # 每边留白（相对源图边长）
    blur_ratio = 0.06         # 投影模糊半径
    offset_ratio = 0.045      # 投影向下偏移
    alpha_ratio = 0.45        # 投影不透明度

    w, h = src.size
    pad = int(w * pad_ratio)
    canvas = Image.new('RGBA', (w + pad * 2, h + pad * 2), (0, 0, 0, 0))

    # 用 alpha 通道做柔和黑色投影
    shadow = Image.new('RGBA', src.size, (0, 0, 0, 0))
    alpha = src.getchannel('A').point(lambda a: int(a * alpha_ratio))
    shadow.putalpha(alpha)
    shadow = shadow.filter(ImageFilter.GaussianBlur(w * blur_ratio))

    offset = int(w * offset_ratio)
    canvas.alpha_composite(shadow, (pad, pad + offset))
    canvas.alpha_composite(src, (pad, pad))
    canvas.save(os.path.join(OUT, 'icon_shadow.png'))
    print('icon_shadow.png:', canvas.size)


def main() -> None:
    assert os.path.isfile(SRC), f'source icon missing: {SRC}'
    src = Image.open(SRC).convert('RGBA')
    assert src.size[0] == src.size[1], 'source icon must be square'
    os.makedirs(OUT, exist_ok=True)
    build_ico(src)
    build_png(src)
    build_shadow(src)


if __name__ == '__main__':
    main()
