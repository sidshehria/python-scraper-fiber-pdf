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
    """Extracts a parameter's value for a specific fiber count from a table."""
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

def _get_tube_type(text: str) -> str:
    """Determines if the cable is Unitube or Multitube."""
    if "Unitube" in text: return "Unitube"
    if "Multitube" in text: return "Multitube"
    match = re.search(r"Number of loose tubes\s*.*?(\d+)", text, re.IGNORECASE)
    if match: return "Unitube" if int(match.group(1)) == 1 else "Multitube"
    return "N/A"

def _get_raw_fiber_type(text: str) -> str:
    """Gets the specific fiber standard like G.652D."""
    match = re.search(r"Fibre Type\s*\"?([^\n\"]*G\.65\d[^\n\"]*|OM\d)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip().replace('$', '').replace('"', '')
    return "N/A"

def _get_environmental_performance(text: str) -> str:
    """Extracts the environmental performance data."""
    match = re.search(r"Environmental Performance\s*([\s\S]*?)IEC-60794-1-22-F1", text)
    if not match:
        return "N/A"
    
    block = match.group(1)
    lines = [line.strip() for line in block.split('\n') if line.strip()]
    
    # Extract temperatures and their conditions
    conditions = {}
    for i in range(len(lines)):
        if '°C' in lines[i]:
            temp_range = lines[i]
            # Condition is usually the next line
            if i + 1 < len(lines):
                condition = lines[i+1].capitalize()
                conditions[condition] = temp_range

    return '  '.join([f"{k} {v}" for k, v in conditions.items()])

def _get_tube_colors(text: str) -> str:
    """Extracts the tube color coding."""
    match = re.search(r"Tube Colour\s*.*\n\s*([\w\s,]+)\n", text, re.IGNORECASE)
    if match:
        colors = [color.strip() for color in re.split(r'\s{2,}|,', match.group(1).strip()) if color]
        return ", ".join(colors)
    return "N/A"

def _build_descriptive_strings(text: str, base_description: str, fc: str) -> (str, str):
    """Builds the detailed cableDescription and typeofCable strings."""
    keywords = []
    if "Indoor" in text: keywords.append("Indoor")
    if "LSZH" in text: keywords.append("LSZH")
    if "Armoured" in text: keywords.append("armoured")
    
    tube_type = _get_tube_type(text)
    if tube_type == "Unitube":
        keywords.append("unitube")
    elif tube_type == "Multitube":
        keywords.append("loose-tube")

    keywords.append("cable")
    typeofCable_str = " ".join(keywords).capitalize()
    
    # Build main description
    desc_suffix = "Fibre Loose Tube" if "loose-tube" in typeofCable_str.lower() else "Fibre Cable"
    cableDescription_str = f"{fc}F {base_description.replace(f'{fc}F','').strip()} {desc_suffix}"
    
    return cableDescription_str, typeofCable_str

def _parse_single_datasheet(filename: str, text: str) -> List[Dict[str, Any]]:
    """Parses text from a single datasheet, returning a list of cable data dicts."""
    results = []
    base_description = _get_cable_description(text)
    
    title_fcs = re.findall(r'\d+', re.split(r'[a-zA-Z]', base_description)[0])
    text_fcs = re.findall(r'(\d+)F', text)
    fiber_counts = sorted(list(set(title_fcs + text_fcs)), key=int)

    if not fiber_counts: return []

    # Common values for the whole document
    raw_fiber_type = _get_raw_fiber_type(text)
    env_conditions = _get_environmental_performance(text)
    tube_colors = _get_tube_colors(text)
    tube_type_str = _get_tube_type(text)

    for fc in fiber_counts:
        tensile_patterns = [r"[\s\S]*?(?:Installation|Short Term)\s*[:\s]*(\d+\s*N)", r"[\s\S]*?(\d+\s*N)"]
        crush_patterns = [r"[\s\S]*?(\d+\s*N[/0-9\s.xcm]+)", r"[\s\S]*?(\d+\s*N)"]
        
        tensile = _get_value_from_table(text, fiber_counts, fc, 'Tensile Strength') or _get_generic_value(text, 'Tensile Strength', tensile_patterns)
        crush = _get_value_from_table(text, fiber_counts, fc, 'Crush Resistance') or _get_generic_value(text, 'Crush Resistance', crush_patterns)
        diameter = _get_value_from_table(text, fiber_counts, fc, 'Cable Diameter')
        
        if not diameter:
            match = re.search(r"Cable Diameter\s*.*?(\d+\.\d+\s*±\s*\d+\.\d+\s*mm)", text, re.IGNORECASE)
            if match: diameter = match.group(1)

        cableDesc, typeofCable = _build_descriptive_strings(text, base_description, fc)

        data = {
            "cableID": 0,
            "cableDescription": cableDesc,
            "fiberCount": f"{fc}F",
            "typeofCable": typeofCable,
            "span": "N/A",
            "tube": tube_type_str,
            "tubeColorCoding": tube_colors,
            "fiberType": raw_fiber_type,
            "diameter": diameter.replace('*', '±') if diameter else "N/A",
            "tensile": tensile,
            "nescCondition": env_conditions,
            "crush": crush.replace('$', '') if crush else "N/A",
            "blowingLength": "N/A",
            "datasheetURL": filename,
            "isActive": "Y"
        }
        results.append(data)
    return results

def parse_datasheets(files: Dict[str, str]) -> List[Dict[str, Any]]:
    """Main function to parse multiple datasheet files."""
    all_cables = []
    current_id = 0
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