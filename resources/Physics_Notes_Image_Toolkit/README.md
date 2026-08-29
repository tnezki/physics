# Physics Notes Image Toolkit v1.0

## Purpose
This package is a **Physics-only Hewitt/source-textbook image inventory for Notes planning**.
It does not own question structures, graph generation, assessment rules, or Notes prose.
`_question_structure/` remains a separate universal authority.

## Inventory
- Catalog entries: **439**
- Unique image hashes: **437**
- Source: the prior Physics textbook visual catalog, verified against the supplied extracted textbook package.
- All cataloged Physics textbook images are retained, including duplicate catalog entries when they represent distinct source placements.

## Workflow
1. **4A Build Notes Map** searches/browses this catalog first and sequences the visual story for each Notes section.
2. Existing mapped EX/YTI anchors are placed where they naturally belong in that story.
3. When a reading/visual beat needs student processing and no mapped EX/YTI belongs there, 4A inserts a **Stop & Discuss**.
4. **4B Build Notes** writes the substantial conceptual reading around the approved map and uses the mapped images.

## Notes image rules
- Use Hewitt images generously when they advance the conceptual story.
- Images are instructional evidence/models/phenomena, not decoration.
- Several images may develop one idea when each adds something different.
- An image is not permanently assigned to one curriculum section; `curriculum_unit` and `curriculum_section` are prior mapping hints only.
- 4A may reuse a strong image in another Notes context when the instructional purpose genuinely differs.
- The `what_students_should_notice_candidate` field is a planning hint, not mandatory final prose.

## Files
- `IMAGE_CATALOG.html` — visual browser with search and unit/story-role filters.
- `IMAGE_CATALOG.json` — machine-readable full catalog for PMs.
- `IMAGE_CATALOG.csv` — spreadsheet-friendly inventory.
- `images/` — all cataloged Physics textbook images, organized by prior curriculum unit.
- `version_manifest.json` — package metadata and counts.
