#!/usr/bin/env python3
import argparse
import json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("--text", required=True)
    args = parser.parse_args()

    translated = f"[{args.dest}] {args.text}"
    payload = {
        "translated": translated,
        "provider_used": "cli",
        "engine": "dummy",
    }
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
