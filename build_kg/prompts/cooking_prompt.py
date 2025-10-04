"""
Reference:
 - Prompts are adapted from [graphrag](https://github.com/microsoft/graphrag)
"""

GRAPH_FIELD_SEP = "<SEP>"
PROMPTS = {}

PROMPTS[
    "claim_extraction"
] = """-Target activity-
You are an intelligent assistant that helps a human analyst to analyze claims against certain entities presented in a text document.

-Goal-
Given a text document that is potentially relevant to this activity, an entity specification, and a claim description, extract all entities that match the entity specification and all claims against those entities.

-Steps-
1. Extract all named entities that match the predefined entity specification. Entity specification can either be a list of entity names or a list of entity types.
2. For each entity identified in step 1, extract all claims associated with the entity. Claims need to match the specified claim description, and the entity should be the subject of the claim.
For each claim, extract the following information:
- Subject: name of the entity that is subject of the claim, capitalized. The subject entity is one that committed the action described in the claim. Subject needs to be one of the named entities identified in step 1.
- Object: name of the entity that is object of the claim, capitalized. The object entity is one that either reports/handles or is affected by the action described in the claim. If object entity is unknown, use **NONE**.
- Claim Type: overall category of the claim, capitalized. Name it in a way that can be repeated across multiple text inputs, so that similar claims share the same claim type
- Claim Status: **TRUE**, **FALSE**, or **SUSPECTED**. TRUE means the claim is confirmed, FALSE means the claim is found to be False, SUSPECTED means the claim is not verified.
- Claim Description: Detailed description explaining the reasoning behind the claim, together with all the related evidence and references.
- Claim Date: Period (start_date, end_date) when the claim was made. Both start_date and end_date should be in ISO-8601 format. If the claim was made on a single date rather than a date range, set the same date for both start_date and end_date. If date is unknown, return **NONE**.
- Claim Source Text: List of **all** quotes from the original text that are relevant to the claim.

Format each claim as (<subject_entity>{tuple_delimiter}<object_entity>{tuple_delimiter}<claim_type>{tuple_delimiter}<claim_status>{tuple_delimiter}<claim_start_date>{tuple_delimiter}<claim_end_date>{tuple_delimiter}<claim_description>{tuple_delimiter}<claim_source>)

3. Return output in English as a single list of all the claims identified in steps 1 and 2. Use **{record_delimiter}** as the list delimiter.

4. When finished, output {completion_delimiter}

-Examples-
Example 1:
Entity specification: recipe
Claim description: allergen presence or cooking-time guarantees
Text:
Recipe: Pesto Pasta.
Cuisine: Italian. Course: Dinner. Diet type: Vegetarian.
Ingredients: Pasta, Basil, Garlic, Parmesan, Olive Oil, Pine Nuts.
Instructions: Toss cooked pasta with basil pesto made from basil, garlic, Parmesan, olive oil, and pine nuts.
Note (2024/05/01): The dish contains tree nuts. The pesto sauce is ready in 5 minutes once ingredients are blended.

Output:

(PESTO PASTA{tuple_delimiter}PINE NUTS{tuple_delimiter}ALLERGEN{tuple_delimiter}TRUE{tuple_delimiter}2024-05-01T00:00:00{tuple_delimiter}2024-05-01T00:00:00{tuple_delimiter}The recipe contains a tree-nut ingredient (pine nuts) as stated in the note.{tuple_delimiter}"The dish contains tree nuts."){record_delimiter}
(PESTO PASTA{tuple_delimiter}NONE{tuple_delimiter}COOKING-TIME{tuple_delimiter}SUSPECTED{tuple_delimiter}2024-05-01T00:00:00{tuple_delimiter}2024-05-01T00:00:00{tuple_delimiter}The note claims the pesto sauce is ready in 5 minutes; this refers to sauce prep time, not total dish time.{tuple_delimiter}"The pesto sauce is ready in 5 minutes once ingredients are blended.")
{completion_delimiter}

Example 2:
Entity specification: Pesto Pasta, Pine Nuts
Claim description: allergen presence or substitutions
Text:
Recipe: Pesto Pasta.
Ingredients: Pasta, Basil, Garlic, Parmesan, Olive Oil, Pine Nuts.
Instructions: Blend pesto; toss with pasta.
Tip (2024/06/10): Sunflower seeds can be substituted for pine nuts.

Output:

(PESTO PASTA{tuple_delimiter}PINE NUTS{tuple_delimiter}ALLERGEN{tuple_delimiter}TRUE{tuple_delimiter}2024-06-10T00:00:00{tuple_delimiter}2024-06-10T00:00:00{tuple_delimiter}Pine nuts are listed as an ingredient and are a tree-nut allergen.{tuple_delimiter}"Ingredients: ... Pine Nuts."){record_delimiter}
(PINE NUTS{tuple_delimiter}SUNFLOWER SEEDS{tuple_delimiter}SUBSTITUTION{tuple_delimiter}TRUE{tuple_delimiter}2024-06-10T00:00:00{tuple_delimiter}2024-06-10T00:00:00{tuple_delimiter}The text states sunflower seeds can be used instead of pine nuts.{tuple_delimiter}"Sunflower seeds can be substituted for pine nuts.")
{completion_delimiter}

-Real Data-
Use the following input for your answer.
Entity specification: {entity_specs}
Claim description: {claim_description}
Text: {input_text}
Output: """

PROMPTS[
    "community_report"
] = """You are an AI assistant that helps a human analyst to perform general information discovery. 
Information discovery is the process of identifying and assessing relevant information associated with certain entities (e.g., recipes, ingredients, tools, methods) within a network.

# Goal
Write a comprehensive report of a community, given a list of entities that belong to the community as well as their relationships and optional associated claims. The report will be used to inform decision-makers or cooks about information associated with the community and their potential impact. The content of this report includes an overview of the community's key entities, how they relate procedurally (requires/uses/part-of), substitutions, time/temperature constraints, and noteworthy safety or dietary claims.

If the entities describe a recipe-like community, ensure the summary mentions cuisine/course/diet/category and that at least one finding lists ingredients, tools/appliances, key steps/methods, and any times/temperatures explicitly stated. Do not invent times or temperatures.

# Report Structure

The report should include the following sections:

- TITLE: community's name that represents its key entities - title should be short but specific. When possible, include representative named entities in the title.
- SUMMARY: An executive summary of the community's overall structure, how its entities are related to each other, and significant information associated with its entities.
- IMPACT SEVERITY RATING: a float score between 0-10 that represents the severity of IMPACT posed by entities within the community. IMPACT is the scored importance of a community (e.g., complexity or safety criticality).
- RATING EXPLANATION: Give a single sentence explanation of the IMPACT severity rating.
- DETAILED FINDINGS: A list of 5-10 key insights about the community. Each insight should have a short summary followed by multiple paragraphs of explanatory text grounded according to the grounding rules below. Be comprehensive.

Return output as a well-formed JSON-formatted string with the following format:
    {{
        "title": <report_title>,
        "summary": <executive_summary>,
        "rating": <impact_severity_rating>,
        "rating_explanation": <rating_explanation>,
        "findings": [
            {{
                "summary":<insight_1_summary>,
                "explanation": <insight_1_explanation>
            }},
            {{
                "summary":<insight_2_summary>,
                "explanation": <insight_2_explanation>
            }}
            ...
        ]
    }}

# Grounding Rules
Do not include information where the supporting evidence for it is not provided.

# Example Input
-----------
Text:
```

Entities:

```csv
id,entity,type,description
1,ROASTED PEPPERS AND MUSHROOM TORTILLA PIZZA,recipe,A tortilla-based skillet pizza topped with marinara, mozzarella, onions, mushrooms, olives, and bell peppers.
2,MOZZARELLA CHEESE,ingredient,Cheese used as topping that melts under broiler.
3,CAST IRON SKILLET,tool,Heavy skillet used on stovetop and then in oven.
4,BROILER,appliance,Oven broiler setting used to brown and melt the top.
5,MEXICAN,cuisine,The cuisine label provided by the recipe header.
6,DINNER,course,Course label provided by the recipe header.
7,VEGETARIAN,diet,The diet type provided by the recipe header.
8,BROIL,method,High-heat top-down cooking method in the oven.
9,PREPARATION TIME: 10 MINUTES,time,Stated preparation time.
10,COOKING TIME: 8 MINUTES,time,Stated cooking time.
```

Relationships:

```csv
id,source,target,description
11,ROASTED PEPPERS AND MUSHROOM TORTILLA PIZZA,MOZZARELLA CHEESE,uses: Cheese is spread and melted.
12,ROASTED PEPPERS AND MUSHROOM TORTILLA PIZZA,CAST IRON SKILLET,uses: Pizza is assembled in a greased cast iron skillet.
13,ROASTED PEPPERS AND MUSHROOM TORTILLA PIZZA,BROILER,uses: Skillet is shifted under the broiler to melt/brown top.
14,ROASTED PEPPERS AND MUSHROOM TORTILLA PIZZA,MEXICAN,is-labeled-as: The recipe header states cuisine is Mexican.
15,ROASTED PEPPERS AND MUSHROOM TORTILLA PIZZA,DINNER,is-labeled-as: The recipe header states course is Dinner.
16,ROASTED PEPPERS AND MUSHROOM TORTILLA PIZZA,VEGETARIAN,is-labeled-as: Diet type is Vegetarian.
17,BROIL,ROASTED PEPPERS AND MUSHROOM TORTILLA PIZZA,method-for: Broiling melts the cheese and browns the top.
18,ROASTED PEPPERS AND MUSHROOM TORTILLA PIZZA,PREPARATION TIME: 10 MINUTES,time-for: Prep time as stated.
19,ROASTED PEPPERS AND MUSHROOM TORTILLA PIZZA,COOKING TIME: 8 MINUTES,time-for: Cook time as stated.
```

```
Output:
{{
    "title": "Tortilla Skillet Pizza (Mexican, Vegetarian) — Broil-Finished",
    "summary": "This community centers on a tortilla-based skillet pizza. It links to key ingredients (mozzarella), a primary tool (cast iron skillet), an appliance/method (oven broiler / broil), and labeled attributes (Mexican, Dinner, Vegetarian). Time entities provide explicit prep (10 min) and cook (8 min) durations.",
    "rating": 4.0,
    "rating_explanation": "Procedural complexity is moderate and the broiler step warrants attention to doneness and safety.",
    "findings": [
        {{
            "summary": "Core composition and flow",
            "explanation": "The pizza is assembled in a cast iron skillet, topped with marinara and mozzarella, then moved under a broiler to finish. Relationships show 'uses' for the skillet and broiler and 'method-for' linking 'broil' to the recipe."
        }},
        {{
            "summary": "Cuisine, course, and diet labels are explicitly stated",
            "explanation": "The header labels the recipe as Mexican, Dinner, and Vegetarian. These labels appear as typed entities connected via 'is-labeled-as' relations to the recipe node."
        }},
        {{
            "summary": "Explicit time constraints",
            "explanation": "The recipe states 'Preparation Time: 10 minutes' and 'Cooking Time: 8 minutes', captured as time entities with 'time-for' relations to the recipe. No invented totals are introduced."
        }},
        {{
            "summary": "Heat source and finish",
            "explanation": "The broiler provides top-down heat to melt and brown the cheese. The method is linked to the dish via 'method-for'. Users should monitor browning to prevent burning."
        }}
    ]
}}
# Real Data

Use the following text for your answer. Do not make anything up in your answer.

Text:
```

{input_text}

```

The report should include the following sections:

- TITLE: community's name that represents its key entities - title should be short but specific. When possible, include representative named entities in the title.
- SUMMARY: An executive summary of the community's overall structure, how its entities are related to each other, and significant information associated with its entities.
- IMPACT SEVERITY RATING: a float score between 0-10 that represents the severity of IMPACT posed by entities within the community.  IMPACT is the scored importance of a community.
- RATING EXPLANATION: Give a single sentence explanation of the IMPACT severity rating.
- DETAILED FINDINGS: A list of 5-10 key insights about the community. Each insight should have a short summary followed by multiple paragraphs of explanatory text grounded according to the grounding rules below. Be comprehensive.

Return output as a well-formed JSON-formatted string with the following format:
    {{
        "title": <report_title>,
        "summary": <executive_summary>,
        "rating": <impact_severity_rating>,
        "rating_explanation": <rating_explanation>,
        "findings": [
            {{
                "summary":<insight_1_summary>,
                "explanation": <insight_1_explanation>
            }},
            {{
                "summary":<insight_2_summary>,
                "explanation": <insight_2_explanation>
            }}
            ...
        ]
    }}

# Grounding Rules
Do not include information where the supporting evidence for it is not provided.

Output:
"""

PROMPTS[
    "entity_extraction"
] = """-Goal-
Given a text document that is potentially relevant to this activity and a list of entity types, identify all entities of those types from the text and all relationships among the identified entities.

Domain hint (non-exclusive): If the text includes explicit recipe headers such as
`Recipe:`, `Cuisine:`, `Course:`, `Diet type:`, `Category:`, `Preparation Time:`, `Cooking Time:`,
`Ingredients:`, `Instructions:`, treat them as canonical signals:
- Map `Cuisine`→type `cuisine`; `Course`→`course`; `Diet type`→`diet`; `Category`→`category`.
- Map `Preparation Time` and `Cooking Time` to type `time` (store the **literal** duration; do not invent values).
- Items under `Ingredients` → type `ingredient` (use singular, canonical names; e.g., “bell peppers (capsicum)”→“bell pepper (capsicum)”).
- Tools/pans/ovens → `tool` or `appliance`.
- Verbs in `Instructions` (broil, sauté, preheat, spread) → `method`.
- Individual actions may be extracted as `step` with a concise, imperative title and one-sentence description.
Do not infer missing temperatures or times.

-Steps-
1. Identify all entities. For each identified entity, extract the following information:
- entity_name: Name of the entity, capitalized
- entity_type: One of the following types: [{entity_types}]
- entity_description: Comprehensive description of the entity's attributes and activities
Format each entity as ("entity"{tuple_delimiter}<entity_name>{tuple_delimiter}<entity_type>{tuple_delimiter}<entity_description>

2. From the entities identified in step 1, identify all pairs of (source_entity, target_entity) that are *clearly related* to each other.
For each pair of related entities, extract the following information:
- source_entity: name of the source entity, as identified in step 1
- target_entity: name of the target entity, as identified in step 1
- relationship_description: explanation as to why you think the source entity and the target entity are related to each other
- relationship_strength: a numeric score indicating strength of the relationship between the source entity and target entity
 Format each relationship as ("relationship"{tuple_delimiter}<source_entity>{tuple_delimiter}<target_entity>{tuple_delimiter}<relationship_description>{tuple_delimiter}<relationship_strength>)

3. Return output in English as a single list of all the entities and relationships identified in steps 1 and 2. Use **{record_delimiter}** as the list delimiter.

4. When finished, output {completion_delimiter}

######################
-Examples-
######################
Example 1:

Entity_types: [recipe, ingredient, tool, appliance, method, cuisine, course, diet, time]
Text:
Recipe: Roasted Peppers And Mushroom Tortilla Pizza Recipe. 
Cuisine: Mexican. Course: Dinner. Diet type: Vegetarian.  
Category: Pizza Recipes.  
Preparation Time: 10 minutes
Cooking Time: 8 minutes

Ingredients:
Tortillas, Extra Virgin Olive Oil, Garlic, Mozzarella cheese, Red Yellow or Green Bell Pepper (Capsicum), Onions, Kalamata olives, Button mushrooms. 

Instructions:
Turn oven to broiler; grease a cast iron skillet with olive oil and heat. Mix minced garlic into marinara. Place tortilla, spread sauce, add mozzarella. When cheese begins to melt, add onions, mushrooms, olives, bell peppers. Shift skillet to broiler to brown. Remove and slice.

################
Output:
("entity"{tuple_delimiter}"Roasted Peppers and Mushroom Tortilla Pizza"{tuple_delimiter}"recipe"{tuple_delimiter}"A tortilla-based skillet pizza finished under the broiler with vegetables and mozzarella."){record_delimiter}
("entity"{tuple_delimiter}"Mozzarella cheese"{tuple_delimiter}"ingredient"{tuple_delimiter}"Cheese topping that melts and browns under the broiler."){record_delimiter}
("entity"{tuple_delimiter}"Cast iron skillet"{tuple_delimiter}"tool"{tuple_delimiter}"Heavy skillet used to assemble and then broil-finish the pizza."){record_delimiter}
("entity"{tuple_delimiter}"Broiler"{tuple_delimiter}"appliance"{tuple_delimiter}"Oven broiler providing high top-down heat for browning."){record_delimiter}
("entity"{tuple_delimiter}"Broil"{tuple_delimiter}"method"{tuple_delimiter}"High-heat finishing step to melt cheese and brown the top."){record_delimiter}
("entity"{tuple_delimiter}"Mexican"{tuple_delimiter}"cuisine"{tuple_delimiter}"Cuisine label from the header."){record_delimiter}
("entity"{tuple_delimiter}"Dinner"{tuple_delimiter}"course"{tuple_delimiter}"Course label from the header."){record_delimiter}
("entity"{tuple_delimiter}"Vegetarian"{tuple_delimiter}"diet"{tuple_delimiter}"Diet label from the header."){record_delimiter}
("entity"{tuple_delimiter}"Preparation Time: 10 minutes"{tuple_delimiter}"time"{tuple_delimiter}"Explicit prep time stated in the header."){record_delimiter}
("entity"{tuple_delimiter}"Cooking Time: 8 minutes"{tuple_delimiter}"time"{tuple_delimiter}"Explicit cook time stated in the header."){record_delimiter}
("relationship"{tuple_delimiter}"Roasted Peppers and Mushroom Tortilla Pizza"{tuple_delimiter}"Mozzarella cheese"{tuple_delimiter}"uses: Cheese is spread and melted during broil."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"Roasted Peppers and Mushroom Tortilla Pizza"{tuple_delimiter}"Cast iron skillet"{tuple_delimiter}"uses: Skillet is greased and used to assemble and heat the pizza."{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"Roasted Peppers and Mushroom Tortilla Pizza"{tuple_delimiter}"Broiler"{tuple_delimiter}"uses: The pan is moved under the broiler to finish and brown the top."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"Broil"{tuple_delimiter}"Roasted Peppers and Mushroom Tortilla Pizza"{tuple_delimiter}"method-for: Broiling melts cheese and browns the surface."{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"Roasted Peppers and Mushroom Tortilla Pizza"{tuple_delimiter}"Preparation Time: 10 minutes"{tuple_delimiter}"time-for: Labeled preparation duration."{tuple_delimiter}7){record_delimiter}
("relationship"{tuple_delimiter}"Roasted Peppers and Mushroom Tortilla Pizza"{tuple_delimiter}"Cooking Time: 8 minutes"{tuple_delimiter}"time-for: Labeled cooking duration."{tuple_delimiter}7){completion_delimiter}

#############################
Example 2:

Entity_types: [ingredient, method, tool, time]
Text:
Instructions:
Preheat oven to 200°C. Sauté sliced mushrooms in olive oil until browned, ~6 minutes. Spread marinara on tortilla, sprinkle mozzarella, bake 4–6 minutes.

#############
Output:
("entity"{tuple_delimiter}"Preheat"{tuple_delimiter}"method"{tuple_delimiter}"Bring oven to target temperature before baking."){record_delimiter}
("entity"{tuple_delimiter}"Sauté"{tuple_delimiter}"method"{tuple_delimiter}"Cook quickly in a small amount of oil over medium-high heat."){record_delimiter}
("entity"{tuple_delimiter}"Oven"{tuple_delimiter}"appliance"{tuple_delimiter}"Provides controlled dry heat for baking."){record_delimiter}
("entity"{tuple_delimiter}"Olive oil"{tuple_delimiter}"ingredient"{tuple_delimiter}"Fat used to sauté mushrooms and grease surfaces."){record_delimiter}
("entity"{tuple_delimiter}"6 minutes"{tuple_delimiter}"time"{tuple_delimiter}"Approximate sauté time for browning mushrooms."){record_delimiter}
("relationship"{tuple_delimiter}"Sauté"{tuple_delimiter}"Olive oil"{tuple_delimiter}"consumes: Method uses olive oil as cooking fat."{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"Preheat"{tuple_delimiter}"Oven"{tuple_delimiter}"temp-for: Preheating sets oven temperature before baking."{tuple_delimiter}7){completion_delimiter}
#############################
-Real Data-
######################
Entity_types: {entity_types}
Text: {input_text}
######################
Output:
"""

PROMPTS[
    "hi_entity_extraction"
] = """
Given a text document that is potentially relevant to a list of entity types, identify all entities of those types.

Domain hint (non-exclusive): If the text includes explicit recipe headers such as
`Recipe:`, `Cuisine:`, `Course:`, `Diet type:`, `Category:`, `Preparation Time:`, `Cooking Time:`,
`Ingredients:`, `Instructions:`, treat them as canonical signals (same mapping rules as in entity_extraction).
Do not infer missing temperatures or times.

-Steps-
1. Identify all entities. For each identified entity, extract the following information:
- entity_name: Name of the entity, capitalized
- entity_type: One of the following types: [{entity_types}], normal_entity means that doesn't belong to any other types.
- entity_description: Comprehensive description of the entity's attributes and activities
Format each entity as ("entity"{tuple_delimiter}<entity_name>{tuple_delimiter}<entity_type>{tuple_delimiter}<entity_description>

2. Return output in English as a single list of all the entities identified in step 1. Use **{record_delimiter}** as the list delimiter.

3. When finished, output {completion_delimiter}

######################
-Examples-
######################
Example 1:

Entity_types: [recipe, ingredient, tool, appliance, method, cuisine, course, diet, time]
Text:
Recipe: Roasted Peppers And Mushroom Tortilla Pizza Recipe. 
Cuisine: Mexican. Course: Dinner. Diet type: Vegetarian.  
Preparation Time: 10 minutes
Cooking Time: 8 minutes

Ingredients:
Tortillas, Extra Virgin Olive Oil, Garlic, Mozzarella cheese, Bell Pepper (Capsicum), Onions, Kalamata olives, Button mushrooms. 

Instructions:
Grease a cast iron skillet; heat. Spread marinara, add mozzarella; broil to melt and brown.

################
Output:
("entity"{tuple_delimiter}"Roasted Peppers and Mushroom Tortilla Pizza"{tuple_delimiter}"recipe"{tuple_delimiter}"Tortilla-based pizza with vegetables and mozzarella, finished under broiler."){record_delimiter}
("entity"{tuple_delimiter}"Cast iron skillet"{tuple_delimiter}"tool"{tuple_delimiter}"Pan used for stovetop assembly and oven finishing."){record_delimiter}
("entity"{tuple_delimiter}"Broiler"{tuple_delimiter}"appliance"{tuple_delimiter}"Oven mode providing top-down heat."){record_delimiter}
("entity"{tuple_delimiter}"Mozzarella cheese"{tuple_delimiter}"ingredient"{tuple_delimiter}"Melting cheese topping."){record_delimiter}
("entity"{tuple_delimiter}"Mexican"{tuple_delimiter}"cuisine"{tuple_delimiter}"Cuisine per header."){record_delimiter}
("entity"{tuple_delimiter}"Preparation Time: 10 minutes"{tuple_delimiter}"time"{tuple_delimiter}"Stated prep time."){record_delimiter}
("entity"{tuple_delimiter}"Cooking Time: 8 minutes"{tuple_delimiter}"time"{tuple_delimiter}"Stated cook time."){completion_delimiter}

#############################
Example 2:

Entity_types: [ingredient, method, appliance]
Text:
Preheat oven. Sauté mushrooms in olive oil; bake tortilla pizza until cheese melts.

#############
Output:
("entity"{tuple_delimiter}"Olive oil"{tuple_delimiter}"ingredient"{tuple_delimiter}"Cooking fat for sautéing."){record_delimiter}
("entity"{tuple_delimiter}"Sauté"{tuple_delimiter}"method"{tuple_delimiter}"Cook quickly in oil over medium-high heat."){record_delimiter}
("entity"{tuple_delimiter}"Oven"{tuple_delimiter}"appliance"{tuple_delimiter}"Appliance used for baking."){completion_delimiter}
#############################
-Real Data-
######################
Entity_types: {entity_types}
Text: {input_text}
######################
Output:
"""

PROMPTS[
    "hi_relation_extraction"
] = """
Given a text document that is potentially relevant to a list of entities, identify all relationships among the given identified entities.

When the text is procedural (e.g., recipes), prefer a small canonical vocabulary at the start of each relationship_description:
`requires:` (entity/step needs an ingredient or tool), `uses:` (step uses tool or method),
`consumes:` (step uses ingredient), `produces:` (step yields intermediate or dish),
`precondition-of:`, `part-of:` (step within recipe), `alternative-to:` (method swap),
`substitutes-for:` (ingredient swap), `time-for:` (step ↔ time), `temp-for:` (step ↔ temperature),
`method-for:` (method ↔ recipe), `next-step:` (ordered steps).
Example style: `uses: Step spreads marinara sauce on tortilla`. Do not invent times or temperatures.

-Steps-
1. From the entities given by user, identify all pairs of (source_entity, target_entity) that are *clearly related* to each other.
For each pair of related entities, extract the following information:
- source_entity: name of the source entity, as identified in step 1
- target_entity: name of the target entity, as identified in step 1
- relationship_description: explanation as to why you think the source entity and the target entity are related to each other
- relationship_strength: a numeric score indicating strength of the relationship between the source entity and target entity
 Format each relationship as ("relationship"{tuple_delimiter}<source_entity>{tuple_delimiter}<target_entity>{tuple_delimiter}<relationship_description>{tuple_delimiter}<relationship_strength>)

2. Return output in English as a single list of all the entities and relationships identified in steps 1 and 2. Use **{record_delimiter}** as the list delimiter.

3. When finished, output {completion_delimiter}

######################
-Examples-
######################
Example 1:

Entities: ["Roasted Peppers and Mushroom Tortilla Pizza", "Cast iron skillet", "Broiler", "Mozzarella cheese", "Broil", "Preparation Time: 10 minutes", "Cooking Time: 8 minutes"]
Text:
Grease a cast iron skillet and heat; assemble tortilla pizza with marinara and mozzarella. Move skillet to oven under broiler to melt and brown. Prep is 10 minutes; cooking is 8 minutes.

################
Output:
("relationship"{tuple_delimiter}"Roasted Peppers and Mushroom Tortilla Pizza"{tuple_delimiter}"Cast iron skillet"{tuple_delimiter}"uses: Skillet is the primary vessel for assembly and heating."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"Roasted Peppers and Mushroom Tortilla Pizza"{tuple_delimiter}"Broiler"{tuple_delimiter}"uses: The dish is finished under the broiler for browning."{tuple_delimiter}9){record_delimiter}
("relationship"{tuple_delimiter}"Broil"{tuple_delimiter}"Roasted Peppers and Mushroom Tortilla Pizza"{tuple_delimiter}"method-for: Broiling melts cheese and browns the top."{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"Roasted Peppers and Mushroom Tortilla Pizza"{tuple_delimiter}"Mozzarella cheese"{tuple_delimiter}"consumes: Cheese is applied and melted during cooking."{tuple_delimiter}7){record_delimiter}
("relationship"{tuple_delimiter}"Roasted Peppers and Mushroom Tortilla Pizza"{tuple_delimiter}"Preparation Time: 10 minutes"{tuple_delimiter}"time-for: Labeled preparation duration."{tuple_delimiter}7){record_delimiter}
("relationship"{tuple_delimiter}"Roasted Peppers and Mushroom Tortilla Pizza"{tuple_delimiter}"Cooking Time: 8 minutes"{tuple_delimiter}"time-for: Labeled cooking duration."{tuple_delimiter}7){completion_delimiter}

#############################
Example 2:

Entities: ["Sauté", "Olive oil", "Mushrooms"]
Text:
Sauté sliced mushrooms in olive oil until browned.

#############
Output:
("relationship"{tuple_delimiter}"Sauté"{tuple_delimiter}"Olive oil"{tuple_delimiter}"consumes: Method uses olive oil as cooking fat."{tuple_delimiter}8){record_delimiter}
("relationship"{tuple_delimiter}"Sauté"{tuple_delimiter}"Mushrooms"{tuple_delimiter}"consumes: Mushrooms are cooked using the sauté method."{tuple_delimiter}8){completion_delimiter}
#############################
-Real Data-
######################
Entities: {entities}
Text: {input_text}
######################
Output:
"""

PROMPTS[
    "summarize_entity_descriptions"
] = """You are a helpful assistant responsible for generating a comprehensive summary of the data provided below.
Given one or two entities, and a list of descriptions, all related to the same entity or group of entities.
Please concatenate all of these into a single, comprehensive description. Make sure to include information collected from all the descriptions.
If the provided descriptions are contradictory, please resolve the contradictions and provide a single, coherent summary.
Make sure it is written in third person, and include the entity names so we the have full context.

#######
-Data-
Entities: {entity_name}
Description List: {description_list}
#######
Output:
"""

PROMPTS[
    "entiti_continue_extraction"
] = """There are entities from the original text were missed in the last extraction. 
Now please extract all the entities that were missed before. 
Do not infer or imagine entities that are not explicitly mentioned in the original text.
Add them below using the same format:
"""

PROMPTS[
    "entiti_if_loop_extraction"
] = """Double-check if any entities from the original text were missed. 
Do not infer or imagine entities that are not explicitly mentioned in the original text.
Answer YES | NO if there are still entities that need to be added.
"""

PROMPTS[
    "summary_clusters"
] = """You are tasked with analyzing a set of entity descriptions and a given list of meta attributes. Your goal is to summarize at least one attribute entity for the entity set in the given entity descriptions. And the summarized attribute entity must match the type of at least one meta attribute in the given meta attribute list (e.g., if a meta attribute is "cuisine", the attribute entity could be "Mexican" or "Italian"). And it should be directly relevant to the entities described in the entity description set. The relationship between the entity set and the generated attribute entity should be clear and logical.

-Steps-
1. Identify at least one attribute entity for the given entity description list. For each attribute entity, extract the following information:
- entity_name: Name of the entity, capitalized
- entity_type: One of the following types: [{meta_attribute_list}], normal_entity means that doesn't belong to any other types.
- entity_description: Comprehensive description of the entity's attributes and activities
Format each entity as ("entity"{tuple_delimiter}<entity_name>{tuple_delimiter}<entity_type>{tuple_delimiter}<entity_description>

2. From each given entity, identify all pairs of (source_entity, target_entity) that are *clearly related* to the attribute entities identified in step 1. And there should be no relations between the attribute entities.
For each pair of related entities, extract the following information:
- source_entity: name of the source entity, as given in entity list
- target_entity: name of the target entity, as identified in step 1
- relationship_description: explanation as to why you think the source entity and the target entity are related to each other
- relationship_strength: a numeric score indicating strength of the relationship between the source entity and target entity
 Format each relationship as ("relationship"{tuple_delimiter}<source_entity>{tuple_delimiter}<target_entity>{tuple_delimiter}<relationship_description>{tuple_delimiter}<relationship_strength>)

3. Return output in English as a single list of all the entities and relationships identified in steps 1 and 2. Use **{record_delimiter}** as the list delimiter.

4. When finished, output {completion_delimiter}


######################
-Example-
######################
Input:
Meta attribute list: ["cuisine", "appliance"]
Entity description list: [("Tortilla Pizza","A tortilla-based skillet pizza finished under the broiler."), ("Quesadilla","A folded tortilla dish with melted cheese."), ("Enchiladas","Tortillas rolled around a filling, typically baked with sauce.")]
#######
Output:
("entity"{tuple_delimiter}"Mexican"{tuple_delimiter}"cuisine"{tuple_delimiter}"A cuisine associated with tortilla-based dishes such as tortilla pizza, quesadillas, and enchiladas."){record_delimiter}
("relationship"{tuple_delimiter}"Tortilla Pizza"{tuple_delimiter}"Mexican"{tuple_delimiter}"is-labeled-as: The dish is commonly categorized under Mexican cuisine."{tuple_delimiter}8.5){record_delimiter}
("relationship"{tuple_delimiter}"Quesadilla"{tuple_delimiter}"Mexican"{tuple_delimiter}"is-labeled-as: Quesadilla is a traditional Mexican dish."{tuple_delimiter}9.0){record_delimiter}
("relationship"{tuple_delimiter}"Enchiladas"{tuple_delimiter}"Mexican"{tuple_delimiter}"is-labeled-as: Enchiladas originate from Mexican cuisine."{tuple_delimiter}9.0){completion_delimiter}
#############################
-Real Data-
######################
Input:
Meta attribute list: {meta_attribute_list}
Entity description list: {entity_description_list}
#######
Output:
"""

# TYPE definitions
PROMPTS["DEFAULT_ENTITY_TYPES"] = [
    "organization", "person", "geo", "event",
    # cooking/algorithmic procedural types (added; non-breaking)
    "recipe", "dish", "ingredient", "tool", "appliance",
    "method", "step", "cuisine", "course", "diet", "time",
    "temperature", "quantity", "category"
]
PROMPTS["META_ENTITY_TYPES"] = [
    "organization", "person", "location", "event",
    "product", "technology", "industry", "mathematics", "social sciences",
    # cooking meta attributes (added)
    "cuisine", "course", "diet", "ingredient", "tool", "appliance", "method", "category"
]
PROMPTS["DEFAULT_TUPLE_DELIMITER"] = "<|>"
PROMPTS["DEFAULT_RECORD_DELIMITER"] = "##"
PROMPTS["DEFAULT_COMPLETION_DELIMITER"] = "<|COMPLETE|>"

PROMPTS[
    "local_rag_response"
] = """---Role---

You are a helpful assistant responding to questions about data in the tables provided.


---Goal---

Generate a response of the target length and format that responds to the user's question, summarizing all information in the input data tables appropriate for the response length and format, and incorporating any relevant general knowledge.
If you don't know the answer, just say so. Do not make anything up.
Do not include information where the supporting evidence for it is not provided.

---Target response length and format---

{response_type}


---Data tables---

{context_data}


---Goal---

Generate a response of the target length and format that responds to the user's question, summarizing all information in the input data tables appropriate for the response length and format, and incorporating any relevant general knowledge.

If you don't know the answer, just say so. Do not make anything up.

Do not include information where the supporting evidence for it is not provided.


---Target response length and format---

{response_type}

Add sections and commentary to the response as appropriate for the length and format. Style the response in markdown.
"""

PROMPTS[
    "global_map_rag_points"
] = """---Role---

You are a helpful assistant responding to questions about data in the tables provided.


---Goal---

Generate a response consisting of a list of key points that responds to the user's question, summarizing all relevant information in the input data tables.

You should use the data provided in the data tables below as the primary context for generating the response.
If you don't know the answer or if the input data tables do not contain sufficient information to provide an answer, just say so. Do not make anything up.

Each key point in the response should have the following element:
- Description: A comprehensive description of the point.
- Importance Score: An integer score between 0-100 that indicates how important the point is in answering the user's question. An 'I don't know' type of response should have a score of 0.

The response should be JSON formatted as follows:
{{
    "points": [
        {{"description": "Description of point 1...", "score": score_value}},
        {{"description": "Description of point 2...", "score": score_value}}
    ]
}}

The response shall preserve the original meaning and use of modal verbs such as "shall", "may" or "will".
Do not include information where the supporting evidence for it is not provided.


---Data tables---

{context_data}

---Goal---

Generate a response consisting of a list of key points that responds to the user's question, summarizing all relevant information in the input data tables.

You should use the data provided in the data tables below as the primary context for generating the response.
If you don't know the answer or if the input data tables do not contain sufficient information to provide an answer, just say so. Do not make anything up.

Each key point in the response should have the following element:
- Description: A comprehensive description of the point.
- Importance Score: An integer score between 0-100 that indicates how important the point is in answering the user's question. An 'I don't know' type of response should have a score of 0.

The response shall preserve the original meaning and use of modal verbs such as "shall", "may" or "will".
Do not include information where the supporting evidence for it is not provided.

The response should be JSON formatted as follows:
{{
    "points": [
        {{"description": "Description of point 1", "score": score_value}},
        {{"description": "Description of point 2", "score": score_value}}
    ]
}}
"""

PROMPTS[
    "global_reduce_rag_response"
] = """---Role---

You are a helpful assistant responding to questions about a dataset by synthesizing perspectives from multiple analysts.


---Goal---

Generate a response of the target length and format that responds to the user's question, summarize all the reports from multiple analysts who focused on different parts of the dataset.

Note that the analysts' reports provided below are ranked in the **descending order of importance**.

If you don't know the answer or if the provided reports do not contain sufficient information to provide an answer, just say so. Do not make anything up.

The final response should remove all irrelevant information from the analysts' reports and merge the cleaned information into a comprehensive answer that provides explanations of all the key points and implications appropriate for the response length and format.

Add sections and commentary to the response as appropriate for the length and format. Style the response in markdown.

The response shall preserve the original meaning and use of modal verbs such as "shall", "may" or "will".

Do not include information where the supporting evidence for it is not provided.


---Target response length and format---

{response_type}


---Analyst Reports---

{report_data}


---Goal---

Generate a response of the target length and format that responds to the user's question, summarize all the reports from multiple analysts who focused on different parts of the dataset.

Note that the analysts' reports provided below are ranked in the **descending order of importance**.

If you don't know the answer or if the provided reports do not contain sufficient information to provide an answer, just say so. Do not make anything up.

The final response should remove all irrelevant information from the analysts' reports and merge the cleaned information into a comprehensive answer that provides explanations of all the key points and implications appropriate for the response length and format.

The response shall preserve the original meaning and use of modal verbs such as "shall", "may" or "will".

Do not include information where the supporting evidence for it is not provided.


---Target response length and format---

{response_type}

Add sections and commentary to the response as appropriate for the length and format. Style the response in markdown.
"""

PROMPTS[
    "naive_rag_response"
] = """You're a helpful assistant
Below are the knowledge you know:
{content_data}
---
If you don't know the answer or if the provided knowledge do not contain sufficient information to provide an answer, just say so. Do not make anything up.
Generate a response of the target length and format that responds to the user's question, summarizing all information in the input data tables appropriate for the response length and format, and incorporating any relevant general knowledge.
If you don't know the answer, just say so. Do not make anything up.
Do not include information where the supporting evidence for it is not provided.
---Target response length and format---
{response_type}
"""

PROMPTS["fail_response"] = "Sorry, I'm not able to provide an answer to that question."

PROMPTS["process_tickers"] = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

PROMPTS["default_text_separator"] = [
    # Paragraph separators
    "\n\n",
    "\r\n\r\n",
    # Line breaks
    "\n",
    "\r\n",
    # Sentence ending punctuation
    "。",  # Chinese period
    "．",  # Full-width dot
    ".",  # English period
    "！",  # Chinese exclamation mark
    "!",  # English exclamation mark
    "？",  # Chinese question mark
    "?",  # English question mark
    # Whitespace characters
    " ",  # Space
    "\t",  # Tab
    "\u3000",  # Full-width space
    # Special characters
    "\u200b",  # Zero-width space (used in some Asian languages)
]

