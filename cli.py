import argparse
import os
from formats import get_converter


def main():
    parser = argparse.ArgumentParser(description="Universal file converter")
    parser.add_argument("input", help="Input file path")
    parser.add_argument("--to", required=True, help="Output format (e.g., md)")
    parser.add_argument("--output", help="Output file path (optional)")

    args = parser.parse_args()

    in_path = args.input
    out_fmt = args.to.lower()

    if not os.path.isfile(in_path):
        print(f"❌ File not found: {in_path}")
        return

    ext = os.path.splitext(in_path)[1].lstrip(".").lower()

    converter = get_converter(ext)
    if not converter:
        print(f"❌ No converter for format: {ext}")
        return

    result_text = converter().convert(in_path)

    if args.output:
        out_path = args.output
    else:
        out_path = os.path.splitext(in_path)[0] + f".{out_fmt}"

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(result_text)

    print(f"✅ Converted: {out_path}")


if __name__ == "__main__":
    main()
