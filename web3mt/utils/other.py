from pathlib import Path
from string import ascii_letters, digits, punctuation
from random import choices

project_path = Path(__file__).parent.parent.parent


def generate_random_string(
    length: int = 20, use_digits: bool = True, use_punctuation: bool = False
):
    return "".join(
        choices(
            ascii_letters
            + (digits if use_digits else "")
            + (punctuation if use_punctuation else ""),
            k=length,
        )
    )


if __name__ == '__main__':
    print(generate_random_string())
