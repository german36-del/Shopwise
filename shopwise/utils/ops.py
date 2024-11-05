import re
import os
import hashlib
import json


def save_image_mapping(hash_index, image_mapping, output_folder, supermarket):
    mapping_file = f"{output_folder}/{supermarket}_mapping.json"
    with open(mapping_file, "w") as f:
        json.dump({hash_index: image_mapping}, f)


def load_image_mapping(hash_index, output_folder, supermarket):
    mapping_file = f"{output_folder}/{supermarket}_mapping.json"
    if os.path.exists(mapping_file):
        with open(mapping_file, "r") as f:
            return json.load(f).get(hash_index, [])
    return []


def get_hash(item, product_image):
    # Combine item and product image to create a unique string
    unique_string = f"{item}_{product_image}"
    # Create a hash of the unique string
    return hashlib.md5(
        unique_string.encode()
    ).hexdigest()  # You can choose other hashing algorithms too


def find_matches(pattern_list, candidate_list):
    """
    Finds and returns the indices and values of matches between a list of patterns and a list of candidates.

    Args:
        pattern_list (list): A list of strings representing patterns to match against.
        candidate_list (list): A list of strings representing candidates to check for matches.

    Returns:
        list: A list of tuples, where each tuple contains the index and the matching value from the candidate list.
    """
    coincidences = []
    for i, value in enumerate(candidate_list):
        if value in pattern_list:
            coincidences.append((i, value))

    return coincidences


def is_number(x):
    """
    Checks if the provided input can be converted to a float.

    Args:
        x (any): The input to check.

    Returns:
        bool: True if the input can be converted to a float, False otherwise.
    """
    try:
        float(x)
        return True
    except ValueError:
        return False


def extract_first_number(input_string):
    """
    Extracts the first number found in a string.

    The function uses a regular expression to find either an integer or a decimal number in the input string.

    Args:
        input_string (str): The input string from which to extract the number.

    Returns:
        float or None: The first number found in the string as a float, or None if no number is found.
    """
    match = re.search(r"\d+\.\d+|\d+", input_string)
    if match:
        return float(match.group(0))
    return None


def ensure_folder_exist(path):
    """
    Checks that a folder exists at the specified path, and if it does not exist, creates it.
    This function takes a single string argument representing a filesystem path and ensures
    that a folder exists at that path. It creates all necessary intermediate directories if
    they do not exist. If the operation is successful, or if the folder already exists
    , the function returns True.
    Args:
        path (str): The filesystem path where the folder should exist.
    Returns:
        bool: True if the folder already exists or was created successfully, False otherwise.
    """
    path = str(path)
    separated = path.split(os.path.sep)
    if separated[0] == "":
        separated.pop(0)
        separated[0] = os.path.sep + separated[0]
    exists = True
    for f in range(len(separated)):
        path = (
            os.path.sep.join(separated[: f + 1])
            if f > 0
            else (separated[0] + os.path.sep)
        )
        if not os.path.exists(path):
            os.mkdir(path)
            exists = False
    return exists
