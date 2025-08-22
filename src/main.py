import os
import json
import pdfplumber
from pathlib import Path
from scraper import parse_datasheets

def main():
    """
    Entry point of the script. Reads PDF files from the data directory,
    processes them, and saves the output as separate JSON files for each fiber count.
    """
    project_root = Path(__file__).parent.parent
    data_dir = project_root / "data"
    output_dir = project_root / "output"

    output_dir.mkdir(exist_ok=True)

    if not data_dir.is_dir():
        print(f"Error: Input directory not found at '{data_dir}'")
        return

    file_contents = {}
    pdf_files = list(data_dir.glob("*.pdf"))

    if not pdf_files:
        print(f"No PDF files found in '{data_dir}'.")
        return

    print("--- Starting PDF Scraping Process ---")
    
    for pdf_path in pdf_files:
        print(f"Reading file: {pdf_path.name}")
        try:
            with pdfplumber.open(pdf_path) as pdf:
                full_text = "".join(page.extract_text() + "\n--- PAGE BREAK ---\n" for page in pdf.pages)
                file_contents[pdf_path.name] = full_text
        except Exception as e:
            print(f"--> Failed to read {pdf_path.name}. Error: {e}")

    if not file_contents:
        print("Could not extract text from any PDF files. Exiting.")
        return

    print("\nProcessing extracted text...")
    all_cables_data = parse_datasheets(file_contents)

    if not all_cables_data:
        print("No cable data was extracted. Exiting.")
        return

    print(f"\n--- Saving {len(all_cables_data)} JSON Files ---")
    
    for cable in all_cables_data:
        original_filename = Path(cable['datasheetURL']).stem
        fiber_count = cable['fiberCount']
        
        output_filename = f"{original_filename}_{fiber_count}F.json"
        output_path = output_dir / output_filename

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(cable, f, indent=2)
            print(f"Saved: {output_path.name}")
        except Exception as e:
            print(f"--> Failed to write {output_filename}. Error: {e}")

    print("\n--- Success! ---")
    print(f"All files saved in: {output_dir}")

if __name__ == "__main__":
    main()