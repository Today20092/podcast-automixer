---
status: accepted
---

# Keep the engine and desktop application in one repository

Keep the Python Automix Engine, CLI adapter, React desktop adapter, and Mix Report in one repository while their shared interface and release cadence are still evolving. Separate the applications at the Automix Engine seam rather than at a repository boundary: the CLI and Desktop Shell call the same application-level operations, while audio-processing rules remain inside the engine; reconsider a repository split only after the interface is stable and consumers or release cadences become genuinely independent.
