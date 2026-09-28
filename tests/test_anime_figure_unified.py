#!/usr/bin/env python3
"""Test script for anime figure price tracking implementation

Tests the unified collector with all three sources (Hpoi API, figurememo, MyFigureList)
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from kensho.scraping.anime_figure_unified import (
    UnifiedFigureCollector,
    run_unified_collection,
)


async def test_basic_collection():
    """Test basic collection with MyFigureList only"""
    print("Testing basic collection with MyFigureList...")
    
    collector = UnifiedFigureCollector(
        output_dir=tempfile.mkdtemp(),
        max_figures=3,
        enable_myfigurelist=True,
        enable_hpoi=False,
        enable_figurememo=False,
    )
    
    # Test with known figure IDs
    records = await collector.collect_all_sources(
        figure_ids=['62857', '62858'],
        batch_size=2
    )
    
    assert len(records) > 0, "Should collect at least one record"
    assert 'figure_id' in records[0], "Records should have figure_id"
    assert 'name' in records[0], "Records should have name"
    assert 'lowest_price_jpy' in records[0], "Records should have price"
    
    print(f"✓ Collected {len(records)} records")
    print(f"✓ Sample: {records[0]['name'][:50]}")
    return records


async def test_dataset_export():
    """Test dataset export functionality"""
    print("\nTesting dataset export...")
    
    collector = UnifiedFigureCollector(
        output_dir=tempfile.mkdtemp(),
        max_figures=5,
        enable_myfigurelist=True,
        enable_hpoi=False,
        enable_figurememo=False,
    )
    
    # Create sample records
    records = await collector.collect_all_sources(
        figure_ids=['62857'],
        batch_size=1
    )
    
    if not records:
        print("⚠ No records to export (API may be unavailable)")
        return
    
    # Test JSON export
    output_files = collector.save_dataset(records, format="json")
    assert "jsonl" in output_files, "Should create JSONL file"
    assert "json" in output_files, "Should create JSON file"
    
    # Verify files exist
    for fmt, path in output_files.items():
        assert path.exists(), f"{fmt} file should exist"
        print(f"✓ {fmt} file created: {path.name}")
    
    # Test CSV export
    output_files_csv = collector.save_dataset(records, format="csv")
    assert "csv" in output_files_csv, "Should create CSV file"
    assert output_files_csv["csv"].exists(), "CSV file should exist"
    print(f"✓ CSV file created: {output_files_csv['csv'].name}")


async def test_gumroad_metadata():
    """Test Gumroad metadata generation"""
    print("\nTesting Gumroad metadata generation...")
    
    collector = UnifiedFigureCollector(
        output_dir=tempfile.mkdtemp(),
        max_figures=5,
    )
    
    # Create sample records
    records = await collector.collect_all_sources(
        figure_ids=['62857'],
        batch_size=1
    )
    
    if not records:
        print("⚠ No records for metadata test (API may be unavailable)")
        return
    
    metadata = collector.create_gumroad_metadata(
        records,
        dataset_name="Test Anime Figure Dataset",
        dataset_description="Test dataset for verification"
    )
    
    assert "dataset_name" in metadata, "Metadata should have dataset_name"
    assert "total_figures" in metadata, "Metadata should have total_figures"
    assert metadata["total_figures"] == len(records), "Total figures should match"
    assert "category_distribution" in metadata, "Metadata should have category distribution"
    
    print(f"✓ Metadata generated: {metadata['dataset_name']}")
    print(f"✓ Total figures: {metadata['total_figures']}")
    print(f"✓ Categories: {list(metadata['category_distribution'].keys())}")


async def test_price_calculations():
    """Test price calculation methods"""
    print("\nTesting price calculations...")
    
    collector = UnifiedFigureCollector()
    
    # Test price range
    price_range = collector._get_price_range(1000, 2000)
    assert price_range == "¥1,000 - ¥2,000", f"Price range should be formatted: {price_range}"
    
    # Test price tier
    assert collector._get_price_tier(500) == "budget"
    assert collector._get_price_tier(2000) == "standard"
    assert collector._get_price_tier(5000) == "premium"
    assert collector._get_price_tier(15000) == "high_end"
    assert collector._get_price_tier(30000) == "collector"
    
    print("✓ Price calculations working correctly")


async def test_full_workflow():
    """Test complete workflow with all features"""
    print("\nTesting full workflow...")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        result = await run_unified_collection(
            output_dir=tmpdir,
            max_figures=2,
            enable_myfigurelist=True,
            enable_hpoi=False,
            enable_figurememo=False,
            format="both",
            dataset_name="Full Workflow Test Dataset",
        )
        
        # Check if we got any results (may be 0 if API unavailable)
        if result["records_collected"] == 0:
            print("⚠ No records collected (API may be unavailable)")
            # This is acceptable for the test
            assert result["success"] is True, "Workflow should succeed even with 0 records"
            return
        
        assert result["success"] is True, "Workflow should succeed"
        assert result["records_collected"] > 0, "Should collect records"
        assert "output_files" in result, "Should have output files"
        assert "metadata_file" in result, "Should have metadata file"
        
        print(f"✓ Full workflow completed: {result['records_collected']} records")
        print(f"✓ Output files: {list(result['output_files'].keys())}")
        print(f"✓ Metadata: {result['metadata']['dataset_name']}")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Anime Figure Price Tracking - Implementation Tests")
    print("=" * 60)
    
    try:
        await test_basic_collection()
        await test_dataset_export()
        await test_gumroad_metadata()
        await test_price_calculations()
        await test_full_workflow()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        return True
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
