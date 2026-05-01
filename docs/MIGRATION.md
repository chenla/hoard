# Migrating to Hoard: An AI-Assisted Walkthrough

*Your notes are scattered across apps, folders, and formats. This guide uses AI to turn that mess into a structured hord — in an afternoon, not a month.*

---

## The Problem

You have years of notes. Maybe they're in Obsidian, or a folder of markdown files, or an org-roam database, or some combination. The notes have value — that's why you kept them. But they're tangled: inconsistent naming, broken links, no hierarchy, duplicates you've forgotten about.

Migrating manually is a project you'll never finish. The traditional advice — "just move everything over and clean it up later" — produces a new mess in a different format.

Hoard takes a different approach: **let AI do the structural work.** You provide the raw material and make the judgment calls. The AI reads, classifies, links, and files. You review and correct. The result is a structured knowledge graph, not just a pile of files in a new app.

## Before You Start

You need:

- Hoard installed (`pipx install hoard-git`)
- A git repo for your hord (`git init my-knowledge && cd my-knowledge && hord init`)
- Your existing notes in a directory somewhere
- An AI assistant (Claude Code, or any MCP-compatible agent with Hoard's MCP server configured)

Estimated time: 1–4 hours depending on collection size, with most of that being review rather than manual work.

## Phase 1: Import (10 minutes)

### Dry run first

Always preview what will happen:

```bash
hord import ~/path/to/notes --dry-run -v
```

This auto-detects whether your notes are from Obsidian, Logseq, org-roam, Dendron, Notion, or plain markdown. It shows what would be imported without writing anything.

Check:
- Does the source detection look right? If not, override with `--from obsidian` (or whichever).
- How many files will be imported vs. skipped?
- Are the titles sensible?

### Run the import

```bash
hord import ~/path/to/notes -v
```

What happens:
- Each note gets a UUID (or keeps its existing one if it had one)
- Wikilinks (`[[like this]]`) are resolved to UUID-based links where the target exists in the import set
- YAML frontmatter tags and aliases are preserved
- Empty files are skipped
- Filename collisions are handled automatically

### Compile and review

```bash
hord compile
hord status
```

You now have cards. They're valid but unrefined — most will be typed as `wh:con` (concept) by default, relationships will be sparse, and the vocabulary will be whatever you had before.

## Phase 2: AI-Assisted Classification (30–60 minutes)

This is where AI earns its keep. Start a conversation with your AI assistant and give it access to the hord (via MCP or by pointing it at the directory).

### Step 1: Type audit

Ask the AI to scan your cards and suggest type corrections:

> "Look at my hord. Many cards are typed as wh:con by default. Review the titles and notes, and suggest which ones should be re-typed as wh:per (person), wh:wrk (work/book), wh:pla (place), wh:org (organization), wh:sys (system), or wh:evt (event). Group your suggestions by type."

The AI will produce a list like:

```
Should be wh:per (person):
  - Taiichi_Ohno--4.org → "Taiichi Ohno" is clearly a person
  - W_Edwards_Deming--4.org → person
  ...

Should be wh:wrk (work):
  - Seeing_Like_a_State--4.org → book by James C. Scott
  - The_Diamond_Age--4.org → novel by Neal Stephenson
  ...
```

Review the suggestions. For the ones you agree with, the AI can update the `:TYPE:` property and rename the files (changing the suffix). Or do it yourself:

```bash
# The AI can do this for you, or you can do it card by card
# Edit the file: change :TYPE: wh:con to :TYPE: wh:per
# Rename: mv Taiichi_Ohno--4.org Taiichi_Ohno--7.org
```

### Step 2: Duplicate detection

> "Scan the hord for likely duplicates — cards with very similar titles, or different titles that seem to describe the same concept. List them as pairs."

Common findings:
- "Machine Learning" and "ML" (same concept, different labels)
- "USA" and "United States of America" (same place)
- Two cards about the same book from different import sources

For true duplicates: keep the richer card, add the other's title as a `UF` (Used For) alias:

```bash
hord link add Machine_Learning UF "ML"
```

For near-duplicates that are actually different: add `RT` links between them.

### Step 3: Hierarchy seeding

> "Look at the cards by type. For the concepts (wh:con), suggest a rough hierarchy: which ones are broader terms (BT) for others? Don't try to be exhaustive — just find the obvious parent-child relationships."

The AI might suggest:

```
Toyota Production System
  NT → Kanban
  NT → Jidoka
  NT → Just-in-Time Manufacturing
  NT → Kaizen

Manufacturing
  NT → Lean Manufacturing
  NT → Assembly Line
  NT → Toyota Production System
```

Review, then apply:

```bash
hord link add Kanban BT Toyota_Production_System
hord link add Jidoka BT Toyota_Production_System
# ... etc. Reciprocals (NT) are added automatically
```

Or let the AI do it in batch through MCP.

### Step 4: Relation discovery

Now use the built-in suggestion engine:

```bash
hord link suggest Kanban
hord link suggest "Taiichi Ohno"
```

This finds unlinked cards that share tags, types, or title words. For each suggestion, decide: is this an RT (related), BT/NT (hierarchical), or not actually related?

The AI can also help here:

> "For each of these 10 cards, suggest 3–5 related cards from the hord and what relation type (BT, NT, RT) fits best. Explain your reasoning briefly."

## Phase 3: Blob Integration (15–30 minutes)

If you have PDFs, EPUBs, or other reference files:

```bash
# Add files with citekeys
hord add ~/papers/scott1998.pdf -k scott:1998seeing \
  -t "Seeing Like a State" -a "James C. Scott" --context

hord add ~/books/diamond-age.epub -k stephenson:1995diamond \
  -t "The Diamond Age" -a "Neal Stephenson"
```

For a large collection, ask the AI to help derive citekeys:

> "I have these PDFs in ~/papers/. For each filename, suggest a citekey in author:yearslug format and a title."

The `--context` flag generates a LOD summary file alongside the blob. You (or the AI) can fill these in later — they make the blob content accessible to AI without reading the full PDF.

## Phase 4: Tag Cleanup (10 minutes)

```bash
hord tags
```

This shows all tags in use and whether they have definition cards. Common findings:
- Redundant tags ("lean" and "lean-manufacturing" and "lean_mfg")
- Tags that should be types (a "person" tag instead of wh:per)
- Tags that are too generic to be useful ("important", "todo")

Merge redundant tags by editing cards, or create tag definition cards for the ones worth keeping:

```bash
hord new "Lean" -t tag
```

## Phase 5: Verification (10 minutes)

```bash
hord compile
hord status
hord query <any-card>    # spot-check a few
hord web                 # browse visually
```

Check:
- **Status** should show all cards as fresh (no stale metadata)
- **Query** should show typed relations, not just floating cards
- **Web** interface lets you browse the graph visually — click through relations to verify they make sense

## What "Done" Looks Like

A migrated hord doesn't need to be perfect. It needs to be:

1. **Every card has a UUID and a type.** No more unidentified blobs.
2. **The obvious hierarchies exist.** Major BT/NT relationships are in place. You can always add more later.
3. **Duplicates are merged.** One concept, one card, aliases as UF.
4. **Key relationships are linked.** People to their works, concepts to their parents. RT links between things that are clearly related.
5. **Blobs are in lib/blob/ with citekeys.** You can find your PDFs via `cite:key`.

This is enough for the hord to be useful — for you, for AI agents reading it, and for the thesaurus to grow organically as you add new knowledge.

## What NOT to Do

- **Don't try to build the perfect hierarchy up front.** Hierarchies emerge through use. Start with the obvious parent-child relationships and let the rest develop.
- **Don't manually categorize every card.** Let AI do the bulk classification. Your job is review and correction.
- **Don't import everything.** If you have notes you haven't looked at in years, they might not be worth migrating. Import what you use or expect to use.
- **Don't worry about the vocabulary being "correct."** The thesaurus is a living thing. BT/NT/RT relationships can be revised. UF aliases can be added anytime. Start rough, refine through use.

## Ongoing: The Daily Workflow

After migration, the hord grows through daily use:

- **Capture** quick thoughts: `hord capture "insight" -t tags` or the mobile capture form
- **Create** new cards when concepts solidify: `hord new "Topic" -t con`
- **Link** as you notice connections: `hord link add CardA RT CardB`
- **Add** reference material: `hord add paper.pdf -k author:yearslug`
- **Review** periodically: `hord link suggest` surfaces connections you've missed

The AI assists throughout — suggesting relations, flagging stale cards, helping classify new captures. The hord gets richer with every interaction, and because the structure is explicit (quads, not prose), nothing is lost to ambiguity.

---

*This walkthrough assumes familiarity with the command line. For a GUI-only workflow, run `hord web` and use the browser interface for browsing, creating, and capturing.*
