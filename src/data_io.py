"""functions for saving and loading data."""

from pathlib import Path

RESOURCES = Path("resources/select_problems_and_labels.txt")

def load_problems_and_labels(problem_file: Path = RESOURCES):
    """Load the problems and labels from a file."""
    with open(problem_file, "r") as f:
        lines = f.read().splitlines()
        
        problems = []
        labels = []
        current_block = ""

        for line in lines:
            # ignore lines starting with # or "\n"
            if line.startswith("#") or line == "":
                continue
            # if line starts with "---PROBLEM", then it's a new problem
            if line.startswith("---PROBLEM"):
                labels.append("CODE_BLOCK_START\n" + current_block)
                current_block = ""
                continue
            # if line starts with "CODE_BLOCK_START", then it's a new label
            if line.startswith("CODE_BLOCK_START"):
                problems.append(current_block)
                current_block = ""
                continue
            current_block += line + "\n"

        # add the last label
        labels.append(current_block)
        
        # discard first, empty label
        labels = labels[1:]
    
    return problems, labels

def number_file_name(path: Path) -> Path:
    """Return a path with a file name that does not exist by appending a number to the end of the file name.
    
    args:
        path: the path to the file
    """
    if not path.exists():
        return path
    else:
        for i in range(100):
            temp_path = path.parent / f"{path.stem}_{i}{path.suffix}"
            if not temp_path.exists():
                return temp_path
    raise ValueError(f"Could not find a file name for {path}.")

if __name__ == "__main__":
    problems, labels = load_problems_and_labels()
    for i in range(5):
        print(f"Problem {i}:")
        print(problems[i])
        print(f"Label {i}:")
        print(labels[i])