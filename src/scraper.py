import json
import re
from typing import List, Dict, Any, Optional

def _get_cable_description(text: str) -> str:
    """Extracts the main cable description from the text."""
    match = re.search(r"Technical Specifications\s*\n(.*?)\s*\n", text, re.IGNORECASE | re.DOTALL)
    if match:
        return re.sub(r'\s+', ' ', match.group(1)).strip()
    return "N/A"

def _get_value_from_table(text: str, fiber_counts: List[str], current_fc: str, parameter: str) -> Optional[str]:
    """
    Extracts a parameter's value for a specific fiber count from a table.
    """
    lines = text.split('\n')
    header_index = -1
    col_map = {}

    for i, line in enumerate(lines):
        if "Fibre Count" in line and any(fc + "F" in line for fc in fiber_counts):
            header_index = i
            header_parts = re.split(r',,|,|\s{2,}', line.strip())
            for fc in fiber_counts:
                for idx, part in enumerate(header_parts):
                    if fc + "F" in part:
                        col_map[fc] = idx
            break
            
    if header_index == -1: return None

    for i in range(header_index + 1, len(lines)):
        line = lines[i]
        if parameter.lower() in line.lower():
            value_parts = re.split(r',,|,|\s{2,}', line.strip())
            if current_fc in col_map:
                fc_col = col_map.get(current_fc, 1)
                target_index = fc_col if parameter.lower() in value_parts[0].lower() else fc_col - 1
                if 0 <= target_index < len(value_parts):
                    value = value_parts[target_index].replace('$', '').replace('"', '').strip()
                    if not value and target_index > 0:
                        return value_parts[target_index-1].replace('$', '').replace('"', '').strip()
                    return value
            if len(value_parts) > 1:
                return value_parts[1].replace('$', '').replace('"', '').strip()
    return None

def _get_generic_value(text: str, parameter: str, patterns: List[str]) -> str:
    """Extracts a generic value using a list of regex patterns."""
    for pattern in patterns:
        match = re.search(f"{parameter}{pattern}", text, re.IGNORECASE | re.DOTALL)
        if match: return match.group(1).strip()
    return "N/A"

def _get_cable_type(text: str, fc: str, fiber_counts: list) -> str:
    """Determines if the cable is Unitube (UT) or Multitube (MT)."""
    if "Unitube" in text: return "UT"
    if "Multitube" in text: return "MT"
    
    num_tubes_str = _get_value_from_table(text, fiber_counts, fc, "Number of loose tubes")
    if num_tubes_str and num_tubes_str.isdigit():
        return "UT" if int(num_tubes_str) == 1 else "MT"
    match = re.search(r"Number of loose tubes\s*.*?(\d+)", text, re.IGNORECASE)
    if match: return "UT" if int(match.group(1)) == 1 else "MT"
    return "N/A"

def _get_fiber_type(text: str, fc: str, fiber_counts: list) -> str:
    """Determines if the fiber is Single-Mode (SM) or Multi-Mode (MM)."""
    ft_str = _get_value_from_table(text, fiber_counts, fc, "Fibre Type")
    if ft_str is None:
        match = re.search(r"Fibre Type\s*\"?([^\n\"]*G\.65\d[^\n\"]*|OM\d)", text, re.IGNORECASE)
        ft_str = match.group(1) if match else ""
    if "G.65" in ft_str or "G.65" in text: return "SM"
    if "OM" in ft_str or "OM" in text: return "MM"
    return "N/A"

def _parse_single_datasheet(filename: str, text: str) -> List[Dict[str, Any]]:
    """Parses text from a single datasheet, returning a list of cable data dicts."""
    results = []
    cable_description = _get_cable_description(text)
    
    # --- FIX: Improved fiber count detection logic ---
    # Step 1: Extract numbers from the title (e.g., "24/48/96F...")
    title_fcs = []
    title_match = re.match(r'([\d/]+)F', cable_description)
    if title_match:
        title_fcs = re.findall(r'\d+', title_match.group(1))

    # Step 2: Find all occurrences of "XXF" in the entire document text.
    text_fcs = re.findall(r'(\d+)F', text)
    
    # Step 3: Combine, remove duplicates, and sort.
    fiber_counts = sorted(list(set(title_fcs + text_fcs)), key=int)
    # --- END FIX ---

    if not fiber_counts: return []

    for fc in fiber_counts:
        tensile_patterns = [r"[\s\S]*?Installation\s*:\s*(\d+\s*N)", r"[\s\S]*?Short Term\s*:\s*(\d+\s*N)", r"[\s\S]*?(\d+\s*N)"]
        crush_patterns = [r"[\s\S]*?(\d+\s*N/\d+\s*x?\s*\d*\s*cm)", r"[\s\S]*?(\d+\s*N/\d+\s*x?\s*\d*\s*mm)", r"[\s\S]*?(\d+\s*N)"]
        tensile = _get_value_from_table(text, fiber_counts, fc, 'Tensile Strength') or _get_generic_value(text, 'Tensile Strength', tensile_patterns)
        crush = _get_value_from_table(text, fiber_counts, fc, 'Crush Resistance') or _get_generic_value(text, 'Crush Resistance', crush_patterns)
        diameter = _get_value_from_table(text, fiber_counts, fc, 'Cable Diameter')
        
        if not diameter:
            match = re.search(r"Cable Diameter\s*.*?(\d+\.\d+\s*±\s*\d+\.\d+\s*mm)", text, re.IGNORECASE)
            if match: diameter = match.group(1)

        data = {
            "cableID": 0, "cableDescription": f"{fc}F {re.sub(r'^[0-9/F\\s]+', '', cable_description)}",
            "fiberCount": fc, "typeofCable": _get_cable_type(text, fc, fiber_counts),
            "span": "N/A", "tube": "Standard",
            "tubeColorCoding": next(iter(re.findall(r"(ΕΙΑ/ΤΙΑ\s*-\s*598|DIN VDE 0888)", text)), "N/A"),
            "fiberType": _get_fiber_type(text, fc, fiber_counts), "diameter": diameter, "tensile": tensile,
            "nescCondition": "N/A", "crush": crush, "blowingLength": "N/A",
            "datasheetURL": filename, "isActive": "Y"
        }
        results.append(data)
    return results

def parse_datasheets(files: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Main function to parse multiple datasheet files.
    Args:
        files: A dictionary of {filename: file_text_content}.
    Returns:
        A list of dictionaries, with each dictionary representing a cable variant.
    """
    all_cables = []
    current_id = 1
    for filename, content in files.items():
        try:
            parsed_cables = _parse_single_datasheet(filename, content)
            for cable in parsed_cables:
                cable['cableID'] = current_id
                all_cables.append(cable)
                current_id += 1
        except Exception as e:
            print(f"--> Could not process file {filename}. Error: {e}")
    return all_cables