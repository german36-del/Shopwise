import pytest

from shopwise.utils.ops import extract_first_number, find_matches, is_number


def test_find_matches():
    """Test the find_matches function for various cases.

    This test checks if the find_matches function correctly identifies
    the indices and values from the candidate_list that match the
    pattern_list. It tests:
    - Basic matches with some candidates found.
    - No matches when no candidates match.
    - An empty candidate list.
    - All candidates match the patterns.
    """
    pattern_list = ["apple", "banana", "cherry"]
    candidate_list = ["orange", "banana", "grape", "apple"]
    expected = [(1, "banana"), (3, "apple")]
    assert find_matches(pattern_list, candidate_list) == expected

    pattern_list = ["kiwi", "mango"]
    candidate_list = ["orange", "banana", "grape"]
    expected = []
    assert find_matches(pattern_list, candidate_list) == expected

    pattern_list = ["kiwi", "mango"]
    candidate_list = []
    expected = []
    assert find_matches(pattern_list, candidate_list) == expected

    pattern_list = ["kiwi", "mango", "orange"]
    candidate_list = ["kiwi", "mango", "orange"]
    expected = [(0, "kiwi"), (1, "mango"), (2, "orange")]
    assert find_matches(pattern_list, candidate_list) == expected


def test_is_number():
    """Test the is_number function for validating numeric strings.

    This test checks whether the is_number function correctly identifies
    valid numeric strings (integers and floats) and invalid strings. It tests:
    - Positive and negative numbers.
    - Strings that are not numeric.
    - Edge cases such as empty strings and strings with spaces.
    """
    assert is_number("10")
    assert is_number("10.5")
    assert is_number("-10.5")
    assert is_number("0")
    assert not is_number("abc")
    assert not is_number("10abc")
    assert not is_number(" ")
    assert not is_number("")


def test_extract_first_number():
    """Test the extract_first_number function for extracting numbers from strings.

    This test checks if the extract_first_number function correctly extracts
    the first number from various input strings. It tests:
    - Strings with a single number.
    - Strings with multiple numbers, ensuring the first is extracted.
    - Strings with no numbers, returning None.
    - Edge cases like strings starting with a number and negative numbers.
    """
    assert extract_first_number("The price is 10.5 dollars.") == 10.5
    assert extract_first_number("Your score is 100.") == 100.0
    assert extract_first_number("No numbers here!") is None
    assert extract_first_number("I have 20 apples and 30 oranges.") == 20.0
    assert extract_first_number("Value: 100.5 and 200.5") == 100.5
    assert extract_first_number("123 apples") == 123.0


if __name__ == "__main__":
    pytest.main()
