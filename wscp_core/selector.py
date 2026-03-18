try:
    from textual.app import App
    from textual.widgets import Button, Static, Checkbox
    from textual.containers import Vertical, Horizontal, VerticalScroll
    TEXTUAL_AVAILABLE = True
except Exception:
    TEXTUAL_AVAILABLE = False

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import FuzzyWordCompleter
    PROMPT_TOOLKIT_AVAILABLE = True
except Exception:
    PROMPT_TOOLKIT_AVAILABLE = False


if TEXTUAL_AVAILABLE:
    class AccessSelectorApp(App):
        BINDINGS = [
            ("ctrl+a", "select_all_items", "Select All"),
            ("ctrl+d", "clear_items", "Clear"),
        ]

        CSS = """
        Screen {
            background: #0a0a0a;
            color: #ffffff;
        }
        #title {
            padding: 1 2 0 2;
            text-style: bold;
            color: #ffffff;
        }
        #hint {
            padding: 0 2 1 2;
            color: #bbbbbb;
        }
        #list {
            height: 1fr;
            margin: 0 2;
            border: solid #3a3a3a;
            padding: 0 1;
        }
        #status {
            padding: 1 2 0 2;
            color: #d0d0d0;
        }
        #actions {
            height: auto;
            padding: 1 2;
        }
        Button {
            margin-right: 1;
            min-width: 16;
        }
        Checkbox {
            margin: 0;
            padding: 0 1;
        }
        """

        def __init__(self, entries):
            super().__init__()
            self.entries = entries
            self.status = None

        def compose(self):
            yield Vertical(
                Static("Download Access Selector", id="title"),
                Static("Mouse: click checkboxes to select. Ctrl+A select all, Ctrl+D clear.", id="hint"),
                VerticalScroll(id="list"),
                Static("Selected: 0", id="status"),
                Horizontal(
                    Button("Select All", id="select_all"),
                    Button("Clear", id="clear"),
                    Button("Start Server", id="start", variant="success"),
                    Button("Cancel", id="cancel", variant="error"),
                    id="actions",
                ),
            )

        def on_mount(self) -> None:
            self.status = self.query_one("#status", Static)
            list_view = self.query_one("#list", VerticalScroll)
            for idx, item in enumerate(self.entries):
                icon = "[DIR]" if item["kind"] == "Folder" else "[FILE]"
                cb = Checkbox(f"{icon} {item['rel']}", id=f"entry-{idx}")
                list_view.mount(cb)
            self.update_status()

        def get_selected_indices(self):
            selected = []
            for cb in self.query(Checkbox):
                if cb.value and cb.id and cb.id.startswith("entry-"):
                    selected.append(int(cb.id.split("-", 1)[1]))
            return selected

        def update_status(self):
            self.status.update(f"Selected: {len(self.get_selected_indices())} / {len(self.entries)}")

        def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
            self.update_status()

        def action_select_all_items(self):
            for cb in self.query(Checkbox):
                cb.value = True
            self.update_status()

        def action_clear_items(self):
            for cb in self.query(Checkbox):
                cb.value = False
            self.update_status()

        def on_button_pressed(self, event: Button.Pressed) -> None:
            if event.button.id == "select_all":
                self.action_select_all_items()
            elif event.button.id == "clear":
                self.action_clear_items()
            elif event.button.id == "start":
                selected_indices = self.get_selected_indices()
                if not selected_indices:
                    self.status.update("Select at least one item to continue.")
                    return
                selected_paths = {self.entries[i]["abs"] for i in selected_indices}
                self.exit(selected_paths)
            elif event.button.id == "cancel":
                self.exit(None)


def cli_access_selector(entries):
    if not entries:
        return set()

    selected_indexes = set()
    search_term = ""
    max_show = 30
    active_view = []

    root_names = set()
    for item in entries:
        rel = item["rel"].replace("\\", "/")
        root_names.add(rel.split("/", 1)[0])
    root_indexes = [
        i for i, item in enumerate(entries)
        if item["rel"].replace("\\", "/").split("/", 1)[0] in root_names
        and "/" not in item["rel"].replace("\\", "/")
    ]

    if not root_indexes:
        root_indexes = list(range(len(entries)))

    def print_menu():
        print("\n=== Access Selector ===")
        print("1. Search")
        print("2. List directory and select files")
        print("3. Select all")
        print("4. Done")
        print("q. Quit")
        print(f"Selected: {len(selected_indexes)}")

    def current_filtered_indexes():
        if not search_term:
            return list(range(len(entries)))
        needle = search_term.lower()
        return [
            i for i, item in enumerate(entries)
            if needle in item["rel"].lower() or needle in item["kind"].lower()
        ]

    def print_visible(title, shown):
        print(f"\n--- {title} ---")
        print(f"Visible: {len(shown)} | Selected: {len(selected_indexes)}")
        print("----------------------------------------")
        if not shown:
            print("No entries to show.")
            return
        capped = shown[:max_show]
        for n, idx in enumerate(capped, start=1):
            item = entries[idx]
            mark = "[x]" if idx in selected_indexes else "[ ]"
            kind_mark = "D" if item["kind"] == "Folder" else "F"
            print(f"{n:4d}. {mark} [{kind_mark}] {item['rel']}")
        if len(shown) > len(capped):
            print(f"... showing first {len(capped)} of {len(shown)}.")

    def prompt_search_text():
        if PROMPT_TOOLKIT_AVAILABLE:
            words = [item["rel"] for item in entries]
            completer = FuzzyWordCompleter(words, WORD=True)
            session = PromptSession()
            return session.prompt(
                "search (live suggestions): ",
                completer=completer,
                complete_while_typing=True,
            ).strip()
        return input("search text: ").strip()

    def parse_toggle_numbers(spec, shown):
        toggles = []
        if not spec:
            return toggles
        spec = spec.replace(",", " ")
        parts = [p.strip() for p in spec.split() if p.strip()]
        for part in parts:
            if "-" in part:
                left, right = part.split("-", 1)
                if left.isdigit() and right.isdigit():
                    start = int(left)
                    end = int(right)
                    if start > end:
                        start, end = end, start
                    for num in range(start, end + 1):
                        if 1 <= num <= min(len(shown), max_show):
                            toggles.append(shown[num - 1])
            elif part.isdigit():
                num = int(part)
                if 1 <= num <= min(len(shown), max_show):
                    toggles.append(shown[num - 1])
        return toggles

    while True:
        print_menu()
        try:
            raw = input("action: ").strip()
        except EOFError:
            return set()
        if not raw:
            continue

        lowered = raw.lower()
        if lowered in ("q", "quit", "exit"):
            return set()
        if lowered in ("4", "done", "start"):
            return {entries[i]["abs"] for i in sorted(selected_indexes)}

        if lowered in ("1", "search"):
            term = prompt_search_text()
            search_term = term
            active_view = current_filtered_indexes() if term else root_indexes[:]
            label = f"Search results for '{term}'" if term else "Directory listing"
            print_visible(label, active_view)
            if active_view:
                spec = input(
                    "Do u wanna select files or folders? numbers (q to quit, space-separated or range e.g. 1 3-5): "
                ).strip()
                if spec.lower() in ("q", "quit"):
                    active_view = []
                    continue
                if spec:
                    toggles = parse_toggle_numbers(spec, active_view)
                    if toggles:
                        for idx in toggles:
                            if idx in selected_indexes:
                                selected_indexes.remove(idx)
                            else:
                                selected_indexes.add(idx)
                        print(f"Selected now: {len(selected_indexes)}")
            continue

        if lowered in ("2", "list", "list directory"):
            search_term = ""
            active_view = root_indexes[:]
            print_visible("Directory listing", active_view)
            if active_view:
                spec = input(
                    "Do u wanna select files or folders? numbers (q to quit, space-separated or range e.g. 1 3-5): "
                ).strip()
                if spec.lower() in ("q", "quit"):
                    continue
                if spec:
                    toggles = parse_toggle_numbers(spec, active_view)
                    if toggles:
                        for idx in toggles:
                            if idx in selected_indexes:
                                selected_indexes.remove(idx)
                            else:
                                selected_indexes.add(idx)
                        print(f"Selected now: {len(selected_indexes)}")
                        return {entries[i]["abs"] for i in sorted(selected_indexes)}
            continue

        if lowered in ("3", "all", "select all"):
            target = list(range(len(entries)))
            for idx in target:
                selected_indexes.add(idx)
            print(f"Selected now: {len(selected_indexes)}")
            return {entries[i]["abs"] for i in sorted(selected_indexes)}

        print("Unknown action.")
