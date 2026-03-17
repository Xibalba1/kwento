PROMPT_MASTER_PLOT_AND_ILLUSTRATIONS = """Write a children's book. IMPORTANT!! ENSURE YOUR RESPONSE IS **LESS** THAN 2000 WORDS / 3300 TOTAL_TOKENS.:
 - **Theme**: {theme}
 - **Plot**:
    - Interesting, adventurous, and fun!
    - Relevant in some way to lives or imaginations of the intended audience
- **Book Title**:
  - Should capture the spirit of adventure, theme, and emotion in the story, without being too direct or generic.
  - Aim for a unique, memorable, and evocative title that appeals to children’s imaginations.
  - Avoid overly descriptive titles that summarize the story; instead, think of titles that spark curiosity and wonder about the character’s journey or adventure.
 - **Reading level**: Pre-schoolers.
 - **Characters**:
    - There should be between 1 and 5 characters in the book
    - Characters should have distinct personalities and behaviors
    - Character appearances should be distinct in size, coloring, clothing, facial and body features, and these attributes should distinguish them from one another
    - Any character present in any `page` > `characters_in_this_page` *MUST* also be present *ONCE AND ONLY ONCE* in `characters`
    - Names used in `page` > `characters_in_this_page` must *EXACTLY* match names present in `characters`
 - **Setting**:
    - There should be at least one if not multiple setting changes.
    - Setting changes can be moderate (Ex: moving from one room of a building to another) or dramatic (Ex: traveling from galaxy to another!)
    - Be sure to describe the setting in `illustration` values for each page so that the generated illustrations can maintain visual consistency when there is not a setting change. (Ex: if an elephant and a monkey are climbing a hill, mention the hill in each page when that action is ongoing.)
 - **`book_length_n_pages`**
    - Length may vary as needed, but should be at least 10 pages.
    - The parameter of 10 in the example output format below is an example only
    - number of entries in `pages` should *EXACTLY* match `book_length_n_pages`
    - ensure the number of pages *WILL NOT* result in a response greater than 2000 WORDS / 3300 TOTAL_TOKENS
 - **`illustration_values`**:
    - *DO NOT* include any dialogue or text to be depicted in the image. All dialogue should be in the `text_content_of_this_page` value for a given page.
    - Will be used to generate images, so, to keep them coherent, make sure to mention the setting of the image, even if the setting is the same as in the previous page. The setting should be described in detail in `illustration` values.
    - should include the description of characters' action, poses, movements, and/or facial expression where warranted. We don't want illustrations that are boring or overly static.
 - **`characters`>`appearance`**:
    - should be very descriptive
    - These descriptions will be used to generate multiple images, so we need sufficient detail to generate consistent depictions of the characters. 
 - **Ensure output is valid JSON (i.e. no syntax errors, opening/closing braces match, escape double quotes in strings, etc.)**
 - **Your response length**: *DO NOT EXCEED 2000 WORDS / 3300 TOTAL_TOKENS* Consider this length limit in determing all parameter values!!
 
OUTPUT FORMAT:
"""

TEMPLATE_CHILDRENS_BOOK = """```{"book_title":"The title of the book","book_length_n_pages":10,"characters":[{"name":"<Name of character>","description":"Brief description of character personality, behavior, etc.","appearance":"Detailed physical description of character."},{"name":"<Name of character>","description":"Brief description of character personality, behavior, etc.","appearance":"Detailed physical description of character."}],"plot_synopsis":"Plot synopsis.","pages":[{"page_number":1,"content":{"text_content_of_this_page":"Text content of page. Content should adhere to `plot_synopsis` and advance the plot appropriately.","illustration":"Illustration or graphic content of page","characters_in_this_page":["Character Name 1","Character Name 2"]}},{"page_number":2,"content":{"text_content_of_this_page":"Text content of page. Content should adhere to `plot_synopsis` and advance the plot appropriately.","illustration":"Illustration or graphic content of page","characters_in_this_page":["Character Name 1","Character Name 2"]}}]}```
"""

PROMPT_MASTER_PLOT_AND_ILLUSTRATIONS_V2 = """Write a children's picture book in JSON.

CRITICAL OUTPUT RULES
- Output ONLY valid JSON (no markdown, no code fences, no commentary).
- Use double quotes for all JSON strings.
- Do not include any keys outside the schema below.
- Do not include any dialogue/text inside any "illustration" string.
- Names are case-sensitive and must match EXACTLY across the JSON.

LENGTH / READING LEVEL CONSTRAINTS (enforced via structure)
- Choose "book_length_n_pages" as an integer between 10 and 15.
- The number of entries in "pages" MUST EXACTLY equal "book_length_n_pages".
- Per page text: 1–3 short sentences total, each sentence <= 20 words.
- Vocabulary: simple, concrete words; prefer present tense; avoid abstract concepts.

THEME
{theme}

PLOT REQUIREMENTS
- The story must have a clear toddler-friendly arc:
  - Page 1: hook / curiosity moment
  - Early pages: discovery of a problem or mystery
  - Middle pages: playful attempts and exploration
  - Final pages: satisfying resolution and happy ending
- Include at least 2 setting changes.
- Include at least one clear choice the character(s) make (shown in page text).
- Keep the plot relevant to a child's life/imagination (home, yard, park, toys, animals, imagination play).

CHARACTERS (1 to 5 total)
- Total characters across the entire book: between 1 and 5.
- "characters" is the single source of truth for character names.
- Any name used in any page's "characters_in_this_page" MUST appear ONCE AND ONLY ONCE in "characters".
- "characters_in_this_page" MUST contain ONLY names from "characters" (no nicknames, no roles like "Mom", no new names).
- Each character must have distinct:
  - personality/behavior ("description")
  - physical appearance ("appearance") including 3–5 visual anchors that remain consistent across pages (e.g., hair, outfit, signature item).
- Do not change outfits or major features unless the page text explicitly says so.

SETTINGS (minimal extra structure)
- Add a top-level "settings" array.
- Each setting object must have:
  - "id" (short string like "S1", "S2", etc.)
  - "name" (short label)
  - "visual_anchor_details" (concise but vivid: lighting, key objects, colors, atmosphere)
- Each page MUST include a "setting_id" that matches one of the "settings" ids.
- If the setting does not change from the previous page, reuse the same "setting_id".
- In each page's "illustration", restate the key setting elements so illustrations stay consistent.

ILLUSTRATION GUIDELINES (no text in images)
- Each page "illustration" MUST include:
  - camera framing (close-up / medium / wide)
  - what each character is doing (action/pose)
    - characters should usually be in motion
  - facial expression/mood
  - at least 3 key background elements from the referenced setting
- Absolutely no written words, letters, numbers, signs, captions, or speech bubbles in the illustration description.

BOOK TITLE
- Unique, evocative, curiosity-sparking.
- Avoid generic or overly descriptive titles that summarize the plot.

OUTPUT FORMAT (SCHEMA — do not add/remove keys)
"""

TEMPLATE_CHILDRENS_BOOK_V2 = """{
  "book_title": "The title of the book",
  "book_length_n_pages": 10,
  "characters": [
    {
      "name": "Character Name",
      "description": "Brief description of personality/behavior.",
      "appearance": "Detailed physical description including 3–5 consistent visual anchors."
    }
  ],
  "settings": [
    {
      "id": "S1",
      "name": "Setting name",
      "visual_anchor_details": "Lighting, key objects, colors, atmosphere for visual consistency."
    }
  ],
  "plot_synopsis": "Plot synopsis (<= 60 words).",
  "pages": [
    {
      "page_number": 1,
      "setting_id": "S1",
      "content": {
        "text_content_of_this_page": "1–2 short sentences; each <= 14 words.",
        "illustration": "No text. Include framing, action, expressions, and setting anchors.",
        "characters_in_this_page": ["Character Name"]
      }
    }
  ]
}

Now generate the completed JSON book following all rules above."""

PROMPT_MASTER_PLOT_AND_ILLUSTRATIONS_V3 = """Write a children's book. IMPORTANT!! ENSURE YOUR RESPONSE IS **LESS** THAN 1301 WORDS / 2201 TOTAL_TOKENS.:
 - **Theme**: {theme}
 - **Plot**:
    - Interesting, adventurous, and fun!
    - Relevant in some way to lives or imaginations of the intended audience
- **Book Title**:
  - Should capture the spirit of adventure, theme, and emotion in the story, without being too direct or generic.
  - Aim for a unique, memorable, and evocative title that appeals to children’s imaginations.
  - Avoid overly descriptive titles that summarize the story; instead, think of titles that spark curiosity and wonder about the character’s journey or adventure.
 - **Reading level**: Pre-school.
 - **Characters**:
    - There should be between 1 and 5 characters in the book
    - Characters should have distinct personalities and behaviors
    - Character appearances should be distinct in size, coloring, clothing, facial and body features, and these attributes should distinguish them from one another
    - Any character present in any `page` > `characters_in_this_page` *MUST* also be present *ONCE AND ONLY ONCE* in `characters`
    - Names used in `page` > `characters_in_this_page` must *EXACTLY* match names present in `characters`
 - **Settings**:
    - Add top-level `settings` with at least one, preferably multiple setting changes.
    - Each `settings` entry must include: `id`, `name`, and `visual_anchor_details`.
    - Every page must include `setting_id` that matches one `settings.id`.
    - Reuse `setting_id` when the setting has not changed.
    - In each page `illustration`, describe setting details so generated illustrations remain visually coherent.
 - **`book_length_n_pages`**
    - Length may vary as needed, but should be at least 10 pages.
    - The parameter of 10 in the example output format below is an example only
    - number of entries in `pages` should *EXACTLY* match `book_length_n_pages`
    - ensure the number of pages *WILL NOT* result in a response greater than 1301 WORDS / 2201 TOTAL_TOKENS
 - **`illustration_values`**:
    - *DO NOT* include any dialogue or text to be depicted in the image. All dialogue should be in the `text_content_of_this_page` value for a given page.
    - Will be used to generate images, so, to keep them coherent, make sure to mention the setting of the image, even if the setting is the same as in the previous page. The setting should be described in detail in `illustration` values.
    - should include the description of characters' action, poses, movements, and/or facial expression where warranted. We don't want illustrations that are boring or overly static.
 - **`characters`>`appearance`**:
    - should be very descriptive
    - These descriptions will be used to generate multiple images, so we need sufficient detail to generate consistent depictions of the characters.
 - **Ensure output is valid JSON (i.e. no syntax errors, opening/closing braces match, escape double quotes in strings, etc.)**
 - **Your response length**: *DO NOT EXCEED 1301 WORDS / 2201 TOTAL_TOKENS* Consider this length limit in determing all parameter values!!

OUTPUT FORMAT:
"""

TEMPLATE_CHILDRENS_BOOK_V3 = """```{"book_title":"The title of the book","book_length_n_pages":10,"characters":[{"name":"<Name of character>","description":"Brief description of character personality, behavior, etc.","appearance":"Detailed physical description of character."},{"name":"<Name of character>","description":"Brief description of character personality, behavior, etc.","appearance":"Detailed physical description of character."}],"settings":[{"id":"S1","name":"<Setting name>","visual_anchor_details":"Lighting, key objects, colors, atmosphere for visual consistency."},{"id":"S2","name":"<Setting name>","visual_anchor_details":"Lighting, key objects, colors, atmosphere for visual consistency."}],"plot_synopsis":"Plot synopsis.","pages":[{"page_number":1,"setting_id":"S1","content":{"text_content_of_this_page":"Text content of page. Content should adhere to `plot_synopsis` and advance the plot appropriately.","illustration":"Illustration or graphic content of page","characters_in_this_page":["Character Name 1","Character Name 2"]}},{"page_number":2,"setting_id":"S1","content":{"text_content_of_this_page":"Text content of page. Content should adhere to `plot_synopsis` and advance the plot appropriately.","illustration":"Illustration or graphic content of page","characters_in_this_page":["Character Name 1","Character Name 2"]}},{"page_number":3,"setting_id":"S2","content":{"text_content_of_this_page":"Text content of page. Content should adhere to `plot_synopsis` and advance the plot appropriately.","illustration":"Illustration or graphic content of page","characters_in_this_page":["Character Name 1","Character Name 2"]}}]}```
"""

THEMES = [
    "Embracing individuality and self-expression",
    "The value of kindness in everyday life",
    "Overcoming fears through bravery",
    "Finding joy in helping others",
    "The beauty of imagination and creativity",
    "Exploring the wonders of nature",
    "Building confidence by facing challenges",
    "Respecting different cultures and perspectives",
    "The power of teamwork and collaboration",
    "Discovering the magic of friendship",
    "Learning from mistakes and failure",
    "Developing patience in a fast-paced world",
    "The importance of honesty and trust",
    "Exploring the power of dreams and goals",
    "The joy of learning and asking questions",
    "Protecting the environment and loving animals",
    "Understanding the value of family and togetherness",
    "The adventure of trying new things",
    "Being compassionate and caring for others",
    "Celebrating diversity and differences",
    "Standing up for what’s right, even when it’s hard",
    "Building a growth mindset and loving learning",
    "Developing a love for music and art",
    "The importance of responsibility and doing your best",
    "Accepting change and adapting to new situations",
    "The joy of giving and sharing with others",
    "Persevering when things get tough",
    "Learning how to be a good listener",
    "Building healthy habits and self-care",
    "Appreciating the little things in life",
    "Cultivating curiosity and exploring the unknown",
    "Understanding emotions and expressing them",
    "The importance of sharing and generosity",
    "Facing loneliness and discovering self-worth",
    "Building empathy and understanding others' feelings",
    "Balancing fun with hard work",
    "Appreciating the power of forgiveness",
    "Managing conflicts with kindness and wisdom",
    "Finding strength in family bonds",
    "Discovering that home is more than just a place",
]

ILLUSTRATION_STYLE_ATTRIBUTES = [
    {
        "style_id": "cut_paper_collage",
        "style_display_name": "cut-paper collage",
        "style_brief": "Build the image as hand-cut paper collage with flat stacked shapes, torn edges, visible paper grain, and no painted or ink-led rendering.",
        "must_have_visual_traits": [
            "flat stacked paper pieces with clearly cut or torn edges",
            "visible paper grain and layered construction across characters and background",
            "broad shape-led characters instead of drawn contour lines",
            "limited high-contrast palette with large blocks of color",
        ],
        "must_not_have_visual_traits": [
            "ink-led outlines",
            "transparent watercolor washes",
            "matte gouache brushwork",
            "slick digital gradients or glossy 3D shading",
        ],
        "visual_anchor_cues": [
            "paper edges remain visible on faces, clothing, and props",
            "overlapping paper layers create shallow handmade depth",
            "background elements read as assembled cut shapes rather than painted scenery",
        ],
        "immutable_attributes": [
            "hand-cut paper collage construction",
            "flat layered depth",
            "visible paper grain and edge texture",
            "shape-built characters with minimal linework",
        ],
        "flexible_attributes": [
            "camera framing can vary by page",
            "composition can open up or tighten around the action",
            "character poses can become more active while remaining shape-led",
        ],
        "Dimensionality/Depth": "Flat layered collage depth",
        "Color Palette": "Limited bold blocks with crisp contrast",
        "Line Quality": "Minimal drawn line; edges come from cut paper shapes",
        "Texture": "Visible paper grain and rough torn-edge texture",
        "Character Style": "Shape-built, simplified, playful",
        "Perspective": "Flat stage-like layering",
        "Movement": "Flexible action shown through pose, not style drift",
        "Composition": "Bold shape groupings with a clear silhouette read",
        "Use of Space": "Full-page layered shapes with strong figure-ground separation",
        "Lighting": "Shallow collage shadows rather than painted light modeling",
        "Mood/Atmosphere": "Handmade, graphic, playful",
        "Medium": "Cut paper collage",
        "Detail Level": "Simple forms with tactile construction detail",
    },
    {
        "style_id": "cozy_ink_watercolor",
        "style_display_name": "ink-led watercolor",
        "style_brief": "Lead with delicate ink drawing and transparent watercolor washes so the image feels drawn first and painted second, with visible line leadership throughout.",
        "must_have_visual_traits": [
            "fine visible ink contours around faces, hands, fabrics, and key objects",
            "transparent watercolor washes sitting underneath the ink drawing",
            "airy interior details and small observed objects rendered through linework",
            "restrained palette with subtle color transitions rather than opaque paint blocks",
        ],
        "must_not_have_visual_traits": [
            "gouache-like opaque paint massing",
            "collage edges or paper-cut construction",
            "graphic cartoon silhouettes with heavy simplification",
            "airbrushed digital polish or photoreal rendering",
        ],
        "visual_anchor_cues": [
            "ink detail remains visible after color is applied",
            "watercolor blooms appear inside larger painted shapes",
            "small room details are described with line rather than paint mass",
        ],
        "immutable_attributes": [
            "ink-led drawing",
            "transparent watercolor wash behavior",
            "line-described objects and features",
            "airier observed detail density",
        ],
        "flexible_attributes": [
            "composition can become more dynamic during action",
            "camera distance can shift from close-up to wide shot",
            "background density can lighten when focus should stay on the characters",
        ],
        "Dimensionality/Depth": "Light perspective built from line and wash",
        "Color Palette": "Restrained watercolor hues with transparent layering",
        "Line Quality": "Fine ink contours with visible internal drawing",
        "Texture": "Paper tooth plus watercolor bloom",
        "Character Style": "Observed, lightly whimsical, line-led",
        "Perspective": "Drawn room depth with readable spatial cues",
        "Movement": "Scene-responsive but still line-led",
        "Composition": "Readable scenes supported by drawing detail",
        "Use of Space": "Interior and environmental details carried by linework",
        "Lighting": "Wash-based light passages rather than opaque paint modeling",
        "Mood/Atmosphere": "Intimate, drawn, domestic",
        "Medium": "Ink and watercolor",
        "Detail Level": "Fine drawing with selective wash detail",
    },
    {
        "style_id": "bold_cartoon_watercolor",
        "style_display_name": "graphic cartoon watercolor",
        "style_brief": "Push the image toward graphic cartoon readability with oversized silhouettes, punchy color blocking, bold shape contrast, and simplified backgrounds that serve the action.",
        "must_have_visual_traits": [
            "large instantly readable silhouettes",
            "punchy saturated color blocks with minimal subtle modulation",
            "facial expressions and poses exaggerated for quick read",
            "backgrounds simplified so the characters dominate the page",
        ],
        "must_not_have_visual_traits": [
            "literary ink-and-wash delicacy",
            "opaque gouache painterliness",
            "dense atmospheric watercolor softness",
            "realistic anatomy or photoreal texture",
        ],
        "visual_anchor_cues": [
            "character bodies read first as bold graphic masses",
            "color blocking creates the main focal contrast",
            "secondary background elements stay simplified and subordinate",
        ],
        "immutable_attributes": [
            "graphic silhouette-first rendering",
            "high-chroma color blocking",
            "exaggerated cartoon posing",
            "background simplification around action",
        ],
        "flexible_attributes": [
            "composition can swing from centered to dynamic diagonals",
            "movement intensity should match page action",
            "background simplification can increase during fast scenes",
        ],
        "Dimensionality/Depth": "Shallow graphic depth with strong focal stacking",
        "Color Palette": "High-chroma blocks with strong contrast",
        "Line Quality": "Bold contour emphasis over internal detail",
        "Texture": "Mostly smooth fills with limited watercolor variation",
        "Character Style": "Exaggerated cartoon action",
        "Perspective": "Dynamic but simplified",
        "Movement": "Energetic and exaggerated",
        "Composition": "Action-first with immediate readability",
        "Use of Space": "Strong focal staging with simplified support elements",
        "Lighting": "Broad simple value separation rather than painterly light",
        "Mood/Atmosphere": "Punchy, funny, kinetic",
        "Medium": "Ink and watercolor",
        "Detail Level": "Simple, high-read, action-dominant",
    },
    {
        "style_id": "airy_pencil_watercolor",
        "style_display_name": "airy pencil watercolor",
        "style_brief": "Keep the image light and open with visible pencil underdrawing, generous untouched paper, pale washes, and fragile sketch energy rather than dense paint coverage.",
        "must_have_visual_traits": [
            "pencil underdrawing remains visible across faces, fabrics, and props",
            "large areas of untouched or lightly washed paper",
            "pale translucent color rather than dense paint",
            "sketch energy survives in the final rendering",
        ],
        "must_not_have_visual_traits": [
            "dense full-page paint massing",
            "bold cartoon shape blocking",
            "opaque gouache surfaces",
            "heavy ink leadership or digital polish",
        ],
        "visual_anchor_cues": [
            "construction lines and pencil edges still peek through the paint",
            "white paper functions as active negative space",
            "color fades out softly instead of filling every surface",
        ],
        "immutable_attributes": [
            "visible pencil underdrawing",
            "high white-space usage",
            "pale transparent wash behavior",
            "open lightly populated page design",
        ],
        "flexible_attributes": [
            "action can become more lively while keeping the airy finish",
            "framing can tighten without losing breathing room",
            "supporting details can increase in important story beats",
        ],
        "Dimensionality/Depth": "Light shallow depth with open paper space",
        "Color Palette": "Pale diluted washes and light neutrals",
        "Line Quality": "Delicate pencil sketch lines remain visible",
        "Texture": "Paper surface with faint wash pooling",
        "Character Style": "Sketch-built, light, unobtrusive",
        "Perspective": "Loose and lightly suggested",
        "Movement": "Can be lively without losing lightness",
        "Composition": "Open layouts driven by negative space",
        "Use of Space": "Airy layouts with breathing room",
        "Lighting": "Very light value range with minimal dramatic modeling",
        "Mood/Atmosphere": "Quiet, spacious, delicate",
        "Medium": "Pencil and watercolor",
        "Detail Level": "Minimal to moderate with sketch emphasis",
    },
    {
        "style_id": "urban_mixed_media",
        "style_display_name": "textured mixed media",
        "style_brief": "Render the scene with layered mixed-media surfaces, grouped architectural or object shapes, gritty paper-and-paint texture, and place-specific environmental detail.",
        "must_have_visual_traits": [
            "surface variation that feels built from paint, paper, and rubbed texture",
            "objects grouped into strong design clusters rather than delicate line description",
            "grounded setting details that feel specific to the place",
            "more weight and material presence in walls, floors, furniture, and props",
        ],
        "must_not_have_visual_traits": [
            "clean literary watercolor wash behavior",
            "cut-paper collage construction",
            "light airy white-space design",
            "slick vector polish or glossy 3D finish",
        ],
        "visual_anchor_cues": [
            "walls, floors, or furniture carry rubbed and layered surface texture",
            "props and background shapes cluster into strong design groups",
            "the environment feels inhabited rather than decorative",
        ],
        "immutable_attributes": [
            "layered mixed-media surface treatment",
            "shape-grouped environment design",
            "material texture in the setting",
            "grounded place-specific detail",
        ],
        "flexible_attributes": [
            "composition can be minimal or busier based on setting",
            "camera angle can shift to support movement",
            "detail can cluster around important setting anchors",
        ],
        "Dimensionality/Depth": "Layered medium depth with designed shape clusters",
        "Color Palette": "Grounded muted base with sharp accent pops",
        "Line Quality": "Secondary to texture and grouped shapes",
        "Texture": "Heavy mixed-media surface presence",
        "Character Style": "Grounded simplified forms",
        "Perspective": "Readable spatial depth with environmental weight",
        "Movement": "Fluid when scenes are active",
        "Composition": "Environment-rich with strong clustered masses",
        "Use of Space": "Full-page with tangible setting density",
        "Lighting": "Broad value design over delicate wash lighting",
        "Mood/Atmosphere": "Grounded, tactile, lived-in",
        "Medium": "Mixed media",
        "Detail Level": "Moderate",
    },
    {
        "style_id": "dreamy_watercolor_pencil",
        "style_display_name": "luminous watercolor pencil",
        "style_brief": "Use luminous layered watercolor color and colored-pencil accents to create a glowing atmospheric image with softened edges and a lightly magical sense of air.",
        "must_have_visual_traits": [
            "glowing layered color that feels lit from within",
            "colored-pencil accents sharpening only selected contours and fabrics",
            "soft atmospheric depth and edge falloff",
            "slightly heightened or magical color relationships without losing readability",
        ],
        "must_not_have_visual_traits": [
            "dry pencil-sketch openness",
            "graphic cartoon blocking",
            "opaque gouache massing",
            "hard-edged realism or digital gradient polish",
        ],
        "visual_anchor_cues": [
            "light blooms around focal shapes and color transitions",
            "colored-pencil accents appear selectively rather than everywhere",
            "distant forms soften into atmospheric color",
        ],
        "immutable_attributes": [
            "luminous layered color behavior",
            "colored-pencil accent rendering",
            "atmospheric soft-edge depth",
            "slightly heightened dreamlike color logic",
        ],
        "flexible_attributes": [
            "surreal touches can strengthen during wonder moments",
            "detail density can increase in emotional beats",
            "composition can become more dynamic while retaining softness",
        ],
        "Dimensionality/Depth": "Atmospheric layered depth with soft falloff",
        "Color Palette": "Luminous shifted color with glowing transitions",
        "Line Quality": "Selective colored-pencil accents, not line-led drawing",
        "Texture": "Transparent layered washes with pencil accent texture",
        "Character Style": "Expressive forms softened by atmosphere",
        "Perspective": "Soft depth shaped by color and air",
        "Movement": "Fluid and lyrical",
        "Composition": "Dynamic but dissolved at the edges",
        "Use of Space": "Immersive pages with atmospheric fade",
        "Lighting": "Glowing color-led illumination",
        "Mood/Atmosphere": "Luminous, airy, lightly magical",
        "Medium": "Watercolor and colored pencil",
        "Detail Level": "Detailed",
    },
    {
        "style_id": "humorous_ink_wash",
        "style_display_name": "brushy ink wash",
        "style_brief": "Use loose brushy ink lines, quick wash accents, and economical scene rendering so the page feels nimble, comic, and built from gesture rather than polish.",
        "must_have_visual_traits": [
            "brushy line variation that shows speed and gesture",
            "selective wash accents instead of fully rendered painted surfaces",
            "comic pose exaggeration and elastic facial expressions",
            "economical scenes that keep only the most useful background information",
        ],
        "must_not_have_visual_traits": [
            "careful literary ink detail",
            "dense painterly environmental rendering",
            "graphic cartoon color blocking",
            "slick vector polish or photoreal shading",
        ],
        "visual_anchor_cues": [
            "brush pressure changes are visible inside the linework",
            "many forms are left partially open or only wash-suggested",
            "the background uses shorthand instead of full scenic rendering",
        ],
        "immutable_attributes": [
            "brushy gestural ink line",
            "economical selective wash rendering",
            "comic shorthand scene design",
            "gesture-first character posing",
        ],
        "flexible_attributes": [
            "background detail can expand when the setting matters",
            "color accents can intensify during exciting beats",
            "composition can tilt or stretch to support comedy and action",
        ],
        "Dimensionality/Depth": "Mostly flat with quick depth cues",
        "Color Palette": "Selective accent color over dominant ink structure",
        "Line Quality": "Loose brushy expressive ink lines",
        "Texture": "Ink bleed and wash pooling",
        "Character Style": "Elastic comic exaggeration",
        "Perspective": "Quick readable staging",
        "Movement": "Lively and comedic",
        "Composition": "Open, gesture-first, and comedic",
        "Use of Space": "Selective white space with shorthand scenery",
        "Lighting": "Secondary to line, gesture, and wash accents",
        "Mood/Atmosphere": "Comic, nimble, mischievous",
        "Medium": "Ink wash and watercolor",
        "Detail Level": "Simple to moderate",
    },
    {
        "style_id": "storybook_gouache",
        "style_display_name": "matte gouache painting",
        "style_brief": "Render the image as opaque matte gouache painting with rounded painted masses, visible brush direction, and shape-built forms rather than line-led drawing.",
        "must_have_visual_traits": [
            "opaque matte paint surfaces with visible brush direction",
            "rounded painted masses defining characters and props",
            "clear foreground-midground-background value staging",
            "painted edges that carry the form more than contour lines do",
        ],
        "must_not_have_visual_traits": [
            "fine ink-led drawing",
            "transparent watercolor dominance",
            "paper collage assembly",
            "flat vector minimalism or glossy realism",
        ],
        "visual_anchor_cues": [
            "brush direction remains visible in large painted areas",
            "forms are built from opaque paint masses instead of internal drawing",
            "depth comes from layered paint values and rounded shape massing",
        ],
        "immutable_attributes": [
            "opaque matte gouache surfaces",
            "rounded painted massing",
            "brush-led edge handling",
            "value-based foreground-background staging",
        ],
        "flexible_attributes": [
            "camera framing can vary significantly",
            "action can become broad and animated while keeping rounded forms",
            "detail can concentrate in focal props and settings",
        ],
        "Dimensionality/Depth": "Layered painted depth with solid massing",
        "Color Palette": "Opaque matte color relationships with strong value grouping",
        "Line Quality": "Edges carried primarily by paint shapes",
        "Texture": "Visible gouache brushwork and matte paint tooth",
        "Character Style": "Rounded forms built from paint mass",
        "Perspective": "Painted spatial staging",
        "Movement": "Responsive to scene action",
        "Composition": "Clear layered staging with painted shape hierarchy",
        "Use of Space": "Full-page painted environments with substantial form",
        "Lighting": "Value-shaped painted illumination",
        "Mood/Atmosphere": "Substantial, matte, painterly",
        "Medium": "Gouache",
        "Detail Level": "Moderate to detailed",
    },
    {
        "style_id": "rembrandt_oil_painting",
        "style_display_name": "Rembrandt-style oil painting",
        "style_brief": "Render the image with dramatic chiaroscuro, rich oil paint layering, and lifelike figures emerging from deep shadow with warm, focused illumination.",
        "must_have_visual_traits": [
            "strong chiaroscuro with deep shadows and concentrated light on faces and hands",
            "warm earthy palette dominated by browns, ochres, and muted golds",
            "subtle skin modeling with lifelike texture and tonal transitions",
            "dark, indistinct backgrounds that push the subject forward",
        ],
        "must_not_have_visual_traits": [
            "flat graphic color blocking",
            "visible paper texture or collage construction",
            "high-key bright palette or pastel tones",
            "clean vector edges or digital gradient polish",
        ],
        "visual_anchor_cues": [
            "faces and hands emerge from shadow with soft glowing highlights",
            "light appears directional and theatrical, often from one side",
            "background dissolves into darkness with minimal detail",
        ],
        "immutable_attributes": [
            "dramatic chiaroscuro lighting",
            "oil-based layered paint handling",
            "lifelike human realism with emotional depth",
            "dark atmospheric background treatment",
        ],
        "flexible_attributes": [
            "composition can vary from portrait to narrative scene",
            "lighting intensity can shift while maintaining strong contrast",
            "detail can concentrate in focal areas like faces and hands",
        ],
        "Dimensionality/Depth": "Deep volumetric depth shaped by light and shadow",
        "Color Palette": "Warm, muted earth tones with golden highlights",
        "Line Quality": "Minimal line; forms defined by light and paint modeling",
        "Texture": "Rich oil paint with soft blending and occasional impasto",
        "Character Style": "Highly realistic, emotionally expressive",
        "Perspective": "Naturalistic spatial depth with subdued backgrounds",
        "Movement": "Subtle and restrained, focused on presence rather than action",
        "Composition": "Centered or triangular compositions emphasizing the subject",
        "Use of Space": "Dark negative space framing illuminated figures",
        "Lighting": "Strong directional chiaroscuro with glowing highlights",
        "Mood/Atmosphere": "Intimate, dramatic, contemplative",
        "Medium": "Oil painting",
        "Detail Level": "High in focal areas, minimal in shadowed regions",
    },
    {
        "style_id": "lichtenstein_ben_day",
        "style_display_name": "Ben-Day dot pop art",
        "style_brief": "Render the image in a Roy Lichtenstein-inspired pop art style using bold outlines, flat primary colors, and Ben-Day dot shading to emulate mass-printed comic aesthetics.",
        "must_have_visual_traits": [
            "uniform Ben-Day dot patterns used for shading and tone",
            "thick black contour lines defining all major shapes",
            "flat primary color fills (red, blue, yellow) with minimal blending",
            "high contrast between dots, color fields, and outlines",
        ],
        "must_not_have_visual_traits": [
            "painterly brushwork or visible paint texture",
            "soft gradients or realistic shading",
            "muted or earthy color palettes",
            "organic hand-drawn sketch lines or loose ink work",
        ],
        "visual_anchor_cues": [
            "dot patterns are consistent in size and spacing within regions",
            "shadows and skin tones rendered via dot density rather than blending",
            "speech bubbles or comic-style framing may appear",
        ],
        "immutable_attributes": [
            "Ben-Day dot shading system",
            "bold black contour outlines",
            "flat high-saturation primary color palette",
            "comic-strip visual language",
        ],
        "flexible_attributes": [
            "composition can vary from close-up portraits to action panels",
            "text elements like captions or speech bubbles may be included or omitted",
            "dot scale can shift slightly depending on focal importance",
        ],
        "Dimensionality/Depth": "Flat graphic depth with minimal spatial illusion",
        "Color Palette": "Primary colors with stark black and white contrast",
        "Line Quality": "Thick, clean, uniform black outlines",
        "Texture": "Mechanical dot patterns with no organic variation",
        "Character Style": "Comic-book stylized with exaggerated expressions",
        "Perspective": "Minimal, often flattened or implied",
        "Movement": "Static or panel-driven comic action",
        "Composition": "Panel-like framing with strong focal subjects",
        "Use of Space": "Bold separation of figure and background with graphic clarity",
        "Lighting": "Implied through dot patterns rather than realistic light sources",
        "Mood/Atmosphere": "Bold, ironic, graphic, commercial",
        "Medium": "Print-style pop art",
        "Detail Level": "Selective, with emphasis on graphic clarity over realism",
    },
    {
        "style_id": "90s_anime_cel",
        "style_display_name": "90s anime cel",
        "style_brief": "Render the image in the hand-painted cel animation style of 1990s Japanese TV anime, with clean inked outlines, flat color fills, and limited but deliberate shading for clarity and motion.",
        "must_have_visual_traits": [
            "clean, confident ink outlines with variable line weight",
            "flat color fills with minimal cel-style shadow shapes",
            "large expressive eyes and simplified facial features",
            "spiky or stylized hair shapes with bold silhouettes",
        ],
        "must_not_have_visual_traits": [
            "painterly brush textures or visible paint strokes",
            "soft gradient-heavy digital shading",
            "photorealistic anatomy or lighting",
            "gritty mixed-media or collage construction",
        ],
        "visual_anchor_cues": [
            "shadows appear as hard-edged shapes rather than blended tones",
            "highlights are minimal and often sharply defined",
            "backgrounds may be simpler or separately rendered from characters",
        ],
        "immutable_attributes": [
            "inked cel animation linework",
            "flat color fills with limited shading",
            "stylized anime character proportions",
            "graphic readability for animation clarity",
        ],
        "flexible_attributes": [
            "action intensity can scale from calm scenes to exaggerated combat",
            "camera angles can become dynamic during action sequences",
            "background detail can vary from minimal to moderately detailed",
        ],
        "Dimensionality/Depth": "Shallow to moderate depth with layered character-background separation",
        "Color Palette": "Bright, saturated colors with simple shadow tones",
        "Line Quality": "Clean ink lines with slight variation in thickness",
        "Texture": "Smooth cel-painted surfaces with minimal texture",
        "Character Style": "Stylized anime with expressive faces and dynamic hair",
        "Perspective": "Simple but can become dynamic in action scenes",
        "Movement": "Energetic and exaggerated, built for animation clarity",
        "Composition": "Character-focused with strong silhouette readability",
        "Use of Space": "Foreground characters emphasized against simpler backgrounds",
        "Lighting": "Minimal, with hard-edged shadow shapes indicating form",
        "Mood/Atmosphere": "Energetic, adventurous, emotionally direct",
        "Medium": "Traditional cel animation",
        "Detail Level": "Moderate, optimized for clarity and repetition in animation",
    },
]
PROMPT_PAGE_ILLUSTRATION_PREFACE = """Create an illustration for children's book according to the following specification (follow the specification *EXACTLY*):"""
PROMPT_PAGE_ILLUSTRATION_SEEDED_REFERENCE_NOTE = (
    "Extract and use the illustration style of the attached image. "
    "You are *NOT* editing the attached image. "
    "You are generating a new image as described in `illustration_description` "
    "and `text_content`."
)
PROMPT_PAGE_ILLUSTRATION_BODY = {
    "SYSTEM_NOTES": {
        "1": "*NEVER* depict text in the generated image.",
        "2": "You are *NOT* creating an image of the act of illustration, nor an illustration in a book. You are creating an illustration to be placed in a book.",
        "3": "Characters *MUST* be in action. *NOT* staring at each other or the reader.",
        "4": "Keep the selected visual style internally consistent across the book, but allow poses, expressions, framing, and composition to change from page to page.",
        "5": "Treat immutable style constraints as the book's rendering identity. Use flexible guidance only to support the page's action and staging.",
        "6": "Avoid photoreal rendering, glossy 3D polish, stock-vector simplification, and generic digital painting unless the selected style explicitly calls for it.",
        "7": "Depict each listed character exactly once unless the prompt explicitly requests multiple appearances of that same character in one image.",
        "8": "Render one continuous moment in time, not multiple beats, stages, or time-slices from a sequence.",
        "9": "Do not turn the image into a montage, comic strip, storyboard, repeated motion study, or multi-panel scene unless explicitly requested.",
        "10": "Show motion through pose, gesture, composition, and camera framing, not by repeating the same character's body multiple times.",
        "11": "Before finalizing, verify that each listed character appears only the allowed number of times.",
    },
    "illustration_description": None,  # text description of the page's illustration
    "illustration_style": {
        "Dimensionality/Depth": None,
        "Color Palette": None,
        "Line Quality": None,
        "Texture": None,
        "Character Style": None,
        "Perspective": None,
        "Movement": None,
        "Composition": None,
        "Use of Space": None,
        "Lighting": None,
        "Mood/Atmosphere": None,
        "Medium": None,
        "Detail Level": None,
    },
    "style_id": None,
    "style_display_name": None,
    "style_brief": None,
    "style_must_have_visual_traits": [],
    "style_must_not_have_visual_traits": [],
    "style_visual_anchor_cues": [],
    "style_immutable_constraints": [],
    "style_flexible_guidance": [],
    "characters_in_illustration": [
        # {
        #     "name": None,
        #     "appearance": None,
        #     "count": 1,
        # }
    ],
    "character_cardinality_summary": None,
    "duplication_rule": None,
    "single_moment_rule": None,
    "motion_without_duplication_rule": None,
    "allowed_duplicate_characters": [],
    "text_content": None,  # text that appears on the page (context for illustration)
}
