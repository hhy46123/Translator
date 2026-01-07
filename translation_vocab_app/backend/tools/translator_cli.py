#!/usr/bin/env python3
import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("--text", required=True)
    args = parser.parse_args()

    try:
        from argostranslate import translate as argos_translate  # type: ignore
    except Exception:
        return 2

    translated = argos_translate.translate(args.text, args.src, args.dest)
    if not translated:
        return 3
    sys.stdout.write(translated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
