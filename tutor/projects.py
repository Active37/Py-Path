PROJECTS = [
    {
        "slug": "python-budget",
        "title": "Build a tiny budget tracker",
        "language": "Python",
        "level": "Beginner",
        "summary": "Track purchases and see where your money goes with a small command-line app.",
        "milestones": [
            {
                "slug": "record-expenses",
                "title": "Record expenses with clear data structures",
                "details": "Create a list of expense dictionaries. Give each expense an item name, category, and numeric amount.",
            },
            {
                "slug": "summarize-categories",
                "title": "Summarize totals by category",
                "details": "Loop through the list and accumulate each amount in a dictionary keyed by category.",
            },
            {
                "slug": "add-budget-check",
                "title": "Add a budget check and readable output",
                "details": "Compare the total with a budget value, then print category totals and a clear under- or over-budget message.",
            },
        ],
    },
    {
        "slug": "interactive-checklist",
        "title": "Create an interactive checklist",
        "language": "JavaScript",
        "level": "Beginner",
        "summary": "Build a useful browser checklist that responds to real user actions.",
        "milestones": [
            {
                "slug": "render-items",
                "title": "Render checklist items from JavaScript data",
                "details": "Start with an array of tasks and create visible list items with DOM methods and textContent.",
            },
            {
                "slug": "handle-actions",
                "title": "Add, complete, and remove items",
                "details": "Connect form and button event listeners. Let people add tasks, toggle completion, and remove items.",
            },
            {
                "slug": "save-progress",
                "title": "Persist the checklist in local storage",
                "details": "Save the task array as JSON, restore it when the page loads, and handle an empty first visit.",
            },
        ],
    },
    {
        "slug": "responsive-portfolio",
        "title": "Design a responsive portfolio",
        "language": "HTML & CSS",
        "level": "Beginner",
        "summary": "Turn a short introduction and a few projects into an accessible portfolio page.",
        "milestones": [
            {
                "slug": "page-structure",
                "title": "Create semantic page sections",
                "details": "Build a header, main introduction, project sections, and footer with semantic HTML landmarks.",
            },
            {
                "slug": "visual-system",
                "title": "Apply a consistent type and color system",
                "details": "Choose a small palette and type scale, check text contrast, and reuse CSS custom properties.",
            },
            {
                "slug": "responsive-layout",
                "title": "Make the layout work on small screens",
                "details": "Use a mobile-first layout, add a breakpoint only where the content needs it, and test keyboard focus.",
            },
        ],
    },
]


def get_project(slug):
    return next((project for project in PROJECTS if project["slug"] == slug), None)
