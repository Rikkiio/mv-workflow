"""Download the fonts the engine uses (FONT_FILES in src/mm/text.py) into this folder. All are free Google Fonts
under the SIL Open Font License, fetched from the google/fonts repository on GitHub.

python fonts/fetch_fonts.py [KEY ...]     (keys as in FONT_FILES, e.g. old cinzel; default: all 14, about 93 MB)
If GitHub can't be reached, download the families from fonts.google.com and put the .ttf files here."""
import os
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
FONTS = {   # key in FONT_FILES: (folder in google/fonts, file, family name on fonts.google.com)
    "mincho": ("shipporiminchob1", "ShipporiMinchoB1-ExtraBold.ttf", "Shippori Mincho B1"),
    "mincho_b": ("shipporiminchob1", "ShipporiMinchoB1-Bold.ttf", "Shippori Mincho B1"),
    "old": ("zenoldmincho", "ZenOldMincho-Black.ttf", "Zen Old Mincho"),
    "brush": ("yujisyuku", "YujiSyuku-Regular.ttf", "Yuji Syuku"),
    "boku": ("yujiboku", "YujiBoku-Regular.ttf", "Yuji Boku"),
    "dela": ("delagothicone", "DelaGothicOne-Regular.ttf", "Dela Gothic One"),
    "decol": ("kaiseidecol", "KaiseiDecol-Bold.ttf", "Kaisei Decol"),
    "tokumin": ("kaiseitokumin", "KaiseiTokumin-ExtraBold.ttf", "Kaisei Tokumin"),
    "rampart": ("rampartone", "RampartOne-Regular.ttf", "Rampart One"),
    "antique": ("zenantique", "ZenAntique-Regular.ttf", "Zen Antique"),
    "hina": ("hinamincho", "HinaMincho-Regular.ttf", "Hina Mincho"),
    "reggae": ("reggaeone", "ReggaeOne-Regular.ttf", "Reggae One"),
    "cinzel": ("cinzel", "Cinzel[wght].ttf", "Cinzel"),
    "antique_b1": ("shipporiantiqueb1", "ShipporiAntiqueB1-Regular.ttf", "Shippori Antique B1"),
}


def main():
    keys = sys.argv[1:] or list(FONTS)
    bad = [k for k in keys if k not in FONTS]
    if bad:
        sys.exit(f"unknown font keys {bad}; known: {' '.join(FONTS)}")
    failed = 0
    for k in keys:
        folder, name, family = FONTS[k]
        dst = os.path.join(HERE, name)
        if os.path.exists(dst):
            print(f"have {name}")
            continue
        try:
            urllib.request.urlretrieve(BASE + folder + "/" + urllib.parse.quote(name), dst + ".part")
            os.replace(dst + ".part", dst)
            print(f"got  {name} ({os.path.getsize(dst) // 1024} KB)")
        except OSError as ex:
            failed += 1
            print(f"FAILED {name}: {ex}\n  get it from https://fonts.google.com/specimen/{family.replace(' ', '+')}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
