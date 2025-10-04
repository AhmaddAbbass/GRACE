import pandas as pd
import yaml
from pathlib import Path

# Load config.yaml
with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

input_csv = Path(config["input_csv"])
output_txt = Path(config["output_txt"])

# Ensure parent folder exists
output_txt.parent.mkdir(parents=True, exist_ok=True)

# Read CSV
df = pd.read_csv(input_csv)

# Open output file
with open(output_txt, "w", encoding="utf-8") as out_file:
    for _, row in df.iterrows():
        recipe_title = str(row["recipe_title"])
        cuisine = str(row["cuisine"])
        course = str(row["course"])
        diet = str(row["diet"])
        category = str(row["category"])
        prep_time = str(row["prep_time"])
        cook_time = str(row["cook_time"])
        ingredients = str(row["ingredients"])
        instructions = str(row["instructions"])
        url = str(row["url"])

        # Construct chunk
        chunk = f""" Recipe: {recipe_title}.
Cuisine: {cuisine}. Course: {course}. Diet type: {diet}.
Category: {category}. Preparation Time: {prep_time}. Cooking Time: {cook_time}.
Ingredients: {ingredients.replace('|', ', ')}.
Instructions: {instructions.replace('|', ' ')}.
Summary: This recipe belongs to the {cuisine} cuisine and is typically served as {course}.
It is a {diet.lower()} dish that uses {', '.join(ingredients.split('|')[:3])} among other ingredients.
Reference: {url} """

        # Write with separators
        out_file.write("<sep>\n")
        out_file.write(chunk.strip() + "\n")
        out_file.write("<sep>\n")
