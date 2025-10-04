import pandas as pd
import yaml
from pathlib import Path
import ast  # to safely evaluate string representations of lists

# ----------------------------
# Load configuration
# ----------------------------
with open("config_food20.yaml", "r") as f:
    config = yaml.safe_load(f)

input_csv = Path(config["input_csv"])
output_txt = Path(config["output_txt"])

# Ensure output directory exists
output_txt.parent.mkdir(parents=True, exist_ok=True)

# ----------------------------
# Read the CSV
# ----------------------------
df = pd.read_csv(input_csv)

# ----------------------------
# Standardize column names
# ----------------------------
df = df.rename(columns={
    "Title": "recipe_title",
    "Ingredients": "ingredients",
    "Instructions": "instructions",
})

# ----------------------------
# Fill missing columns with defaults
# ----------------------------
required_columns = [
    "recipe_title", "cuisine", "course", "diet", "category",
    "prep_time", "cook_time", "ingredients", "instructions"
]

for col in required_columns:
    if col not in df.columns:
        df[col] = "Not specified"

# ----------------------------
# Helper: clean ingredient lists
# ----------------------------
def clean_ingredients(raw):
    """
    Convert a stringified list like "['egg', 'milk']" → "egg, milk".
    If it's already text, just return as-is.
    """
    try:
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, list):
            return ", ".join(str(item).strip() for item in parsed)
        else:
            return str(parsed)
    except Exception:
        # if parsing fails, return raw text stripped of brackets/quotes
        return str(raw).replace("[", "").replace("]", "").replace("'", "").replace('"', '').strip()

# ----------------------------
# Write text chunks to output
# ----------------------------
with open(output_txt, "w", encoding="utf-8") as out_file:
    for _, row in df.iterrows():
        recipe_title = str(row["recipe_title"])
        cuisine = str(row["cuisine"])
        course = str(row["course"])
        diet = str(row["diet"])
        category = str(row["category"])
        prep_time = str(row["prep_time"])
        cook_time = str(row["cook_time"])
        ingredients = clean_ingredients(str(row["ingredients"]))
        instructions = str(row["instructions"])

        # Construct chunk (no image info)
        chunk = f""" Recipe: {recipe_title}.
Cuisine: {cuisine}. Course: {course}. Diet type: {diet}.
Category: {category}. Preparation Time: {prep_time}. Cooking Time: {cook_time}.
Ingredients: {ingredients}.
Instructions: {instructions.replace('|', ' ')}.
Summary: This recipe belongs to the {cuisine} cuisine and is typically served as {course}.
It is a {diet.lower()} dish that uses {', '.join(ingredients.split(', ')[:3])} among other ingredients.
"""

        # Write with separators
        out_file.write("<sep>\n")
        out_file.write(chunk.strip() + "\n")
        out_file.write("<sep>\n")

print(f"✅ Successfully wrote all chunks to {output_txt}")
