#!/usr/bin/env python3
import sys

from argostranslate.translate import translate


def main() -> int:
    if len(sys.argv) < 4:
        return 2

    src = sys.argv[1]
    dest = sys.argv[2]
    text = " ".join(sys.argv[3:])

    translated = translate(text, src, dest)
    if not translated:
        return 3
    sys.stdout.write(translated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
