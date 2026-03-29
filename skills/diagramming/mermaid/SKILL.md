---
name: mermaid
description: Create Mermaid diagrams — flowcharts, sequence diagrams, ERDs, Gantt charts, class diagrams, and more — as .mmd or .md files. Renders natively in GitHub, GitLab, Notion, VS Code, and Obsidian. No external tools or API keys required.
version: 1.0.0
author: memosr
license: MIT
prerequisites:
  commands: []
metadata:
  hermes:
    tags: [Mermaid, Diagrams, Flowcharts, Sequence-Diagrams, ERD, Architecture, Visualization]
    related_skills: [excalidraw, github-pr-workflow]
---

# Mermaid Diagrams

Create diagrams as plain text using [Mermaid](https://mermaid.js.org) syntax. Mermaid renders natively in GitHub READMEs, GitLab, Notion, VS Code (with extensions), Obsidian, and many documentation platforms — no image uploads, no external tools, no API keys.

## When to Use

Load this skill when asked to:
- Create a flowchart, architecture diagram, or system overview
- Draw a sequence diagram for an API flow or user journey
- Generate an entity-relationship diagram (ERD) for a database schema
- Make a Gantt chart for a project timeline
- Document class relationships or state machines

## Diagram Types

### Flowchart

```mermaid
flowchart TD
    A[User Request] --> B{Auth Check}
    B -- Pass --> C[Process Request]
    B -- Fail --> D[Return 401]
    C --> E[Return Response]
```

**Save as:** `diagram.mmd` or embed in Markdown as a ` ```mermaid ` code block.

---

### Sequence Diagram

```mermaid
sequenceDiagram
    participant User
    participant API
    participant DB

    User->>API: POST /login
    API->>DB: SELECT user WHERE email=?
    DB-->>API: user row
    API-->>User: 200 OK + JWT
```

---

### Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    USER {
        int id PK
        string email
        string name
    }
    POST {
        int id PK
        int user_id FK
        string title
        text body
    }
    USER ||--o{ POST : "writes"
```

---

### Class Diagram

```mermaid
classDiagram
    class Animal {
        +String name
        +speak() String
    }
    class Dog {
        +fetch() void
    }
    Animal <|-- Dog
```

---

### Gantt Chart

```mermaid
gantt
    title Project Timeline
    dateFormat  YYYY-MM-DD
    section Backend
    API design       :done,    des1, 2026-01-01, 2026-01-05
    Implementation   :active,  des2, 2026-01-06, 2026-01-15
    section Frontend
    UI components    :         des3, 2026-01-10, 2026-01-20
```

---

### State Diagram

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Processing : start
    Processing --> Done : success
    Processing --> Error : failure
    Error --> Idle : retry
    Done --> [*]
```

---

## Workflow

### 1. Write the diagram

Use `write_file` to save a `.mmd` file:

```bash
write_file("architecture.mmd", """
flowchart LR
    Client --> LoadBalancer
    LoadBalancer --> API1
    LoadBalancer --> API2
    API1 --> Database
    API2 --> Database
""")
```

### 2. Embed in Markdown

To embed directly in a README or doc file, wrap in a fenced code block with the `mermaid` language tag:

````markdown
```mermaid
flowchart LR
    A --> B --> C
```
````

GitHub, GitLab, and Notion will render this automatically with no extra tooling.

### 3. Render locally (optional)

If the user has the Mermaid CLI installed:

```bash
# Install
npm install -g @mermaid-js/mermaid-cli

# Render to PNG
mmdc -i architecture.mmd -o architecture.png

# Render to SVG
mmdc -i architecture.mmd -o architecture.svg

# Render with custom theme
mmdc -i architecture.mmd -o architecture.svg -t dark
```

Check availability first:

```bash
if command -v mmdc &>/dev/null; then
    echo "Mermaid CLI available: $(mmdc --version)"
else
    echo "Mermaid CLI not installed. Diagram saved as .mmd for browser/editor rendering."
fi
```

### 4. Preview in browser (no install)

Direct the user to paste the diagram at:
- **https://mermaid.live** — official live editor with real-time preview
- **https://github.com** — paste in any issue, PR, or README comment

## Pitfalls

- **Indentation matters** — use consistent 4-space indentation inside diagram blocks.
- **Special characters in labels** — wrap labels containing `()`, `[]`, or `{}` in quotes: `A["label (detail)"]`.
- **Long labels** — use `<br/>` for line breaks inside node labels: `A["First line<br/>Second line"]`.
- **Subgraphs** — must be closed with `end`:
  ```
  subgraph Backend
      API --> DB
  end
  ```
- **Sequence diagram arrows** — `->>` is solid (sync call), `-->>` is dashed (response). Don't mix them up.
- **GitHub rendering** — GitHub renders Mermaid in Markdown files and issue comments but NOT in raw `.mmd` files viewed directly. For GitHub, always embed in a Markdown file.

## Quick Reference

| Diagram type | Keyword |
|---|---|
| Flowchart | `flowchart TD` / `flowchart LR` |
| Sequence | `sequenceDiagram` |
| Class | `classDiagram` |
| State | `stateDiagram-v2` |
| ERD | `erDiagram` |
| Gantt | `gantt` |
| Pie chart | `pie` |
| Mindmap | `mindmap` |
| Timeline | `timeline` |
