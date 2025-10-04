import json
import yaml
from pathlib import Path

# ----------------------------
# Load config file
# ----------------------------
with open("config_apparel.yaml", "r") as f:
    config = yaml.safe_load(f)

input_json = Path(config["input_json"])
output_txt = Path(config["output_txt"])

# Ensure output directory exists
output_txt.parent.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Read the JSON dataset (line by line JSON objects)
# ----------------------------
data = []
with open(input_json, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:  # skip blank lines
            data.append(json.loads(line))

# ----------------------------
# Helper to safely extract text
# ----------------------------
def safe_str(value):
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v)
    return str(value).strip() if value else "Not specified"

# ----------------------------
# Process each instance
# ----------------------------
with open(output_txt, "w", encoding="utf-8") as out_file:
    for instance in data:
        # ---- Basic fields ----
        title = safe_str(instance.get("Title", "Not specified"))
        ancestors = instance.get("Ancestors", [])
        category = safe_str(instance.get("Category", "Not specified"))
        subject = safe_str(instance.get("Subject", "Not specified"))
        reference = safe_str(instance.get("Url", "Not specified"))

        # ---- Domain hierarchy ----
        hierarchy_text = ""
        for idx, ancestor in enumerate(ancestors):
            hierarchy_text += f"Domain hierarchy {idx+1}: {ancestor}. "

        # ---- Toolbox ----
        tools = instance.get("Toolbox", [])
        tool_names = []
        for tool in tools:
            if isinstance(tool.get("Name"), list):
                tool_names.extend(tool["Name"])
            elif isinstance(tool.get("Name"), str):
                tool_names.append(tool["Name"])
        tools_text = ", ".join(tool_names) if tool_names else "Not specified"

        # ---- Steps ----
        steps = instance.get("Steps", [])
        all_steps = []
        for step in steps:
            text = step.get("Text_raw", "")
            step_tools = step.get("Tools_extracted", [])
            if step_tools and step_tools[0] != "NA":
                text += f" (Tools used: {', '.join(step_tools)})"
            all_steps.append(text.strip())

        instructions = " ".join(all_steps)

        # ---- Build text chunk ----
        chunk = f"""Guide: {title}.
{hierarchy_text.strip()}
Category: {category}. Subject: {subject}.
Tools required: {tools_text}.
Instructions: {instructions}
Reference: {reference}
"""

        # ---- Write to file with separators ----
        out_file.write("<sep>\n")
        out_file.write(chunk.strip() + "\n")
        out_file.write("<sep>\n")

print(f"✅ Successfully wrote transformed Apparel data to {output_txt}")
