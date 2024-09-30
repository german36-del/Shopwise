from collections import namedtuple
from typing import List, Optional

from fuzzywuzzy import process

from shopwise.utils.ops import find_matches, is_number

Product = namedtuple(
    "Product", ["market", "brand", "name", "price", "price_unit_or_kg", "image"]
)


def find_closest_product(products: List[Product], item: str) -> Optional[Product]:
    """
    Finds the closest product match based on the item name.

    Args:
        products (List[Product]): List of Product objects.
        item (str): The item name to match.

    Returns:
        Optional[Product]: The closest matching Product object or None if no match is found.
    """
    product_names = [product.name for product in products]
    result = process.extractOne(item, product_names)
    if result is None:
        return None
    closest_match, score = result
    if score > 70:
        for prod in products:
            if closest_match == prod.name:
                return prod
    return None


def compute_rough_price(
    quantity: str, product: Optional[Product], unit: bool = False
) -> float:
    """
    Computes the total price based on the given quantity and product.

    Args:
        quantity (str): The quantity (e.g., "5", "5 kg", "5 liters", etc.)
        product (Optional[Product]): The product to calculate the price for.

    Returns:
        float: The total price for the given quantity.
    """

    if not product:
        return 0.0

    price_per_unit = product.price
    if unit:
        return price_per_unit * quantity
    price_per_kg = 0.0
    if product.price_unit_or_kg:
        try:
            price_per_kg = float(price_per_unit)
        except ValueError:
            return 0.0

    total_price = 0.0

    try:
        quantity_value = float(quantity)
    except ValueError:
        return 0.0
    total_price = quantity_value * price_per_kg

    return total_price


def process_shoping_list(filepath):
    """
    Processes a shopping list from a specified file and categorizes products based on their measurements.

    This function reads a shopping list from a text file, extracting products that are measured in weight (kilograms, grams, milligrams),
    liquid volume (liters, milliliters), and standard units. It raises errors for invalid or ambiguous entries.

    Args:
        filepath (str): The path to the text file containing the shopping list.

    Returns:
        tuple: A tuple containing three dictionaries:
            - weight_products (dict): A dictionary of products with weights, where keys are product names and values are weights in kilograms.
            - unit_products (dict): A dictionary of products measured in standard units, where keys are product names and values are quantities.
            - liquid_products (dict): A dictionary of liquid products, where keys are product names and values are volumes in liters.

    Raises:
        ValueError: If a line contains more than one metric unit, or if there are invalid weight or volume values.
    """
    weight_products = {}
    unit_products = {}
    liquid_products = {}
    weight_patterns = ["kg", "g", "mg"]
    volume_patterns = ["L", "mL"]

    with open(filepath, encoding="utf-8") as file:
        lines = file.readlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue

            splitted_line = line.split(" ")
            matches_weight = find_matches(weight_patterns, splitted_line)
            matches_volume = find_matches(volume_patterns, splitted_line)

            if matches_weight:
                if len(matches_weight) > 1:
                    raise ValueError(
                        f"Please provide just one metric unit in this line (weight): {line.strip()}"
                    )
                else:
                    filtered_list = [
                        x
                        for i, x in enumerate(splitted_line)
                        if (i != matches_weight[0][0] and x and not is_number(x))
                    ]

                    product_name = " ".join(filtered_list).strip()
                    try:
                        weight_value = float(splitted_line[matches_weight[0][0] - 1])
                    except ValueError:
                        raise ValueError(
                            f"Invalid weight value in line: {line.strip()}"
                        )
                    unit = matches_weight[0][1]

                    if unit == "kg":
                        weight_products[product_name] = weight_value
                    elif unit == "g":
                        weight_products[product_name] = weight_value / 1000
                    elif unit == "mg":
                        weight_products[product_name] = weight_value / 1000000

            if matches_volume:
                if len(matches_volume) > 1:
                    raise ValueError(
                        f"Please provide just one metric unit in this line (volume): {line.strip()}"
                    )
                else:
                    filtered_list = [
                        x
                        for i, x in enumerate(splitted_line)
                        if (i != matches_volume[0][0] and x and not is_number(x))
                    ]

                    product_name = " ".join(filtered_list).strip()
                    try:
                        volume_value = float(splitted_line[matches_volume[0][0] - 1])
                    except ValueError:
                        raise ValueError(
                            f"Invalid volume value in line: {line.strip()}"
                        )
                    unit = matches_volume[0][1]

                    if unit == "L":
                        liquid_products[product_name] = volume_value
                    elif unit == "mL":
                        liquid_products[product_name] = volume_value / 1000

            if not matches_weight and not matches_volume:
                filtered_list = [x for x in splitted_line if x and not is_number(x)]
                if splitted_line and is_number(splitted_line[0]):
                    quantity = float(splitted_line[0])
                    product_name = " ".join(filtered_list).strip()
                    unit_products[product_name] = quantity
                else:
                    raise ValueError(f"Invalid quantity in line: {line.strip()}")

    return weight_products, unit_products, liquid_products
