# Project-Scoped Rules

## Ebook Synchronization and Deduplication
1. **Always Deduplicate during Sync:** Whenever the user requests `/sync` or asks to sync/update ebooks on their Kindles, you MUST execute `python dedupe_all_libraries.py` to identify and remove duplicate EPUB files and their corresponding `.sdr` folders on the local machine and all active Kindles.
2. **Follow Sync Skill Workflow:** Strictly adhere to the workflow defined in [.agents/skills/sync/SKILL.md](file:///C:/Users/admin-beats/Documents/antigravity/hopeful-bose/.agents/skills/sync/SKILL.md).
