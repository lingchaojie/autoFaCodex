import argparse
from pathlib import Path

from autofacodex.contracts import SlideModel
from autofacodex.tools.pptx_generate import generate_pptx


def _default_asset_root(model_path: Path) -> Path:
    if model_path.parent.name == "slides":
        return model_path.parent.parent
    return model_path.parent


def generate_from_model(
    model_path: Path, output_path: Path, asset_root: Path | None = None
) -> Path:
    model = SlideModel.model_validate_json(model_path.read_text(encoding="utf-8"))
    return generate_pptx(
        model,
        output_path,
        asset_root=asset_root if asset_root is not None else _default_asset_root(model_path),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a PPTX candidate from a slide model JSON file."
    )
    parser.add_argument("model_path", type=Path)
    parser.add_argument("output_path", type=Path)
    parser.add_argument("--asset-root", type=Path)
    args = parser.parse_args()
    generate_from_model(args.model_path, args.output_path, args.asset_root)


if __name__ == "__main__":
    main()
