"""Tests for batch processing pipeline."""

from pathlib import Path
import pytest
from docuvision.pipeline.batch import BatchProcessor


@pytest.mark.asyncio
async def test_batch_processor_discover_and_run(tmp_path: Path):
    processor = BatchProcessor()
    examples_dir = Path("examples")

    files = processor.discover_files(examples_dir)
    assert len(files) >= 2

    out_dir = tmp_path / "batch_out"
    result = await processor.process_batch_async(
        input_dir=examples_dir,
        output_dir=out_dir,
        schema_name="generic",
        dpi=150,
        use_vlm=False,
        concurrency=2,
        export_formats=["json", "markdown", "excel"],
    )

    assert result.total_files >= 2
    assert result.successful_files >= 2
    assert result.failed_files == 0
    assert (out_dir / "batch_summary.csv").exists()
    assert (out_dir / "batch_summary.json").exists()

    # Check generated files
    json_files = list(out_dir.glob("*.json"))
    assert len(json_files) >= 3  # 2 file jsons + batch_summary.json
