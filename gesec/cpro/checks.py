
import csv
import glob
import logging
import optparse
import os
import sys

logger = logging.getLogger(__name__)

IDENTIFIANT_CHORUS_PRO_COLUMN = "Identifiant Chorus Pro"


def check_csv_and_downloads(csv_path: str, downloads_path: str) -> tuple[bool, list[str]]:
    """Make sure every lines present in csv are downloaded.
    
    Reads the CSV file, extracts "Identifiant Chorus Pro" column to get a list of IDs,
    then checks in the downloads directory for the presence of files matching "facture_<id>.zip".
    
    Args:
        csv_path: Path to the CSV file containing the "Identifiant Chorus Pro" column
        downloads_path: Path to the directory containing downloaded zip files
    
    Returns:
        A tuple of (all_downloaded, missing_ids) where:
        - all_downloaded: True if all IDs from CSV have corresponding zip files
        - missing_ids: List of IDs from CSV that don't have a corresponding zip file
    """
    # Read CSV and extract IDs from IDENTIFIANT_CHORUS_PRO_COLUMN
    csv_ids = set()
    
    with open(csv_path, "r", newline="", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=";")
        
        # Check if required column exists
        if IDENTIFIANT_CHORUS_PRO_COLUMN not in reader.fieldnames:
            raise ValueError(
                f"CSV must contain '{IDENTIFIANT_CHORUS_PRO_COLUMN}' column. "
                f"Available columns: {reader.fieldnames}"
            )
        
        for row in reader:
            id_chorus = row[IDENTIFIANT_CHORUS_PRO_COLUMN].strip()
            if id_chorus:  # Skip empty IDs
                csv_ids.add(id_chorus)
    
    if not csv_ids:
        return True, []  # No IDs in CSV, nothing to check
    
    # Get list of downloaded files matching pattern facture_<id>.zip
    downloaded_ids = set()
    
    # Use glob.iglob with pattern to efficiently iterate only over facture files
    for filepath in glob.iglob(os.path.join(downloads_path, "facture_*.zip")):
        filename = os.path.basename(filepath)
        # Extract ID from filename: facture_<id>.zip -> <id>
        id_from_filename = filename[len("facture_"):-len(".zip")]
        downloaded_ids.add(id_from_filename)
    
    # Find missing IDs (in CSV but not downloaded)
    missing_ids = sorted(csv_ids - downloaded_ids)
    
    all_downloaded = len(missing_ids) == 0
    
    return all_downloaded, missing_ids


def _count_csv_ids(csv_path: str) -> int:
    """Count the number of non-empty IDs in a CSV file.
    
    Args:
        csv_path: Path to the CSV file
    
    Returns:
        Number of non-empty Identifiant Chorus Pro entries
    """
    count = 0
    with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            if row.get(IDENTIFIANT_CHORUS_PRO_COLUMN, "").strip():
                count += 1
    return count


def check_csv_files(csv_paths: list[str], downloads_path: str) -> tuple[dict[str, tuple[bool, list[str]]], int, int, int]:
    """Check a list of CSV files against downloaded files.
    
    Args:
        csv_paths: List of paths to CSV files to check
        downloads_path: Path to the directory containing downloaded zip files
    
    Returns:
        A tuple of (results, total_all, total_downloaded, total_missing) where:
        - results: Dictionary mapping CSV filenames to (all_downloaded, missing_ids) tuples
        - total_all: Total number of IDs across all CSV files
        - total_downloaded: Total number of downloaded IDs
        - total_missing: Total number of missing IDs
    """
    results = {}
    total_files = len(csv_paths)
    
    logger.info(f"Checking {total_files} CSV file(s)")
    
    total_all = 0
    total_downloaded = 0
    total_missing = 0
    
    for idx, csv_path in enumerate(csv_paths, 1):
        csv_filename = os.path.basename(csv_path)
        logger.info(f"Checking CSV {idx}/{total_files}: {csv_filename}")
        all_downloaded, missing_ids = check_csv_and_downloads(csv_path, downloads_path)
        results[csv_filename] = (all_downloaded, missing_ids)
        
        csv_total = _count_csv_ids(csv_path)
        
        total_all += csv_total
        total_downloaded += csv_total - len(missing_ids)
        total_missing += len(missing_ids)
        
        if not all_downloaded:
            logger.warning(f"  {len(missing_ids)} missing IDs for {csv_filename}")
    
    logger.info(f"Completed checking {total_files} CSV file(s)")
    logger.info(f"Total: {total_all}, Downloaded: {total_downloaded}, Missing: {total_missing}")
    return results, total_all, total_downloaded, total_missing


def check_csvs_directory(csv_dir: str, downloads_path: str) -> tuple[dict[str, tuple[bool, list[str]]], int, int, int]:
    """Check all CSV files in a directory against downloaded files.
    
    Iterates over all .csv files in the specified directory and calls check_csv_files.
    
    Args:
        csv_dir: Path to the directory containing CSV files
        downloads_path: Path to the directory containing downloaded zip files
    
    Returns:
        Same output as check_csv_files: (results, total_all, total_downloaded, total_missing)
    """
    csv_files = list(glob.iglob(os.path.join(csv_dir, "*.csv")))
    return check_csv_files(csv_files, downloads_path)


def parse_args():
    """Parse command line arguments."""
    parser = optparse.OptionParser()
    parser.add_option("--downloads-path", dest="downloads_path", 
                      help="Path to the directory containing downloaded zip files (required)")
    options, args = parser.parse_args()
    return options, args


def main():
    """Main entry point for the script."""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    options, args = parse_args()
    
    # Validate required arguments
    if not options.downloads_path:
        logger.error("Error: --downloads-path is required")
        sys.exit(1)
    
    if not args:
        logger.error("Error: At least one CSV file or directory is required")
        sys.exit(1)
    
    # Collect all CSV files to check
    csv_files = []
    for arg in args:
        if os.path.isdir(arg):
            # If it's a directory, add all CSV files from it
            csv_files.extend(glob.iglob(os.path.join(arg, "*.csv")))
        elif os.path.isfile(arg):
            # If it's a file, add it directly
            csv_files.append(arg)
        else:
            logger.error(f"Error: '{arg}' is not a valid file or directory")
            sys.exit(1)
    
    if not csv_files:
        logger.error("Error: No CSV files found in the provided arguments")
        sys.exit(1)
    
    # Run checks on all collected CSV files
    results, total_all, total_downloaded, total_missing = check_csv_files(
        csv_files, options.downloads_path
    )
    
    all_ok = all(all_dl for all_dl, _ in results.values())
    status = "OK" if all_ok else "NOK"
    logger.info(f"Check result: {status}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
