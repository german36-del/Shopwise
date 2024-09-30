import csv
import json
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from prettytable import PrettyTable

from shopwise.utils import LOGGER, ConfigDict, colorstr
from shopwise.utils.supermarket import (Product, compute_rough_price,
                                        find_closest_product)

from .base import ShopScrapper

SCRAPERS_SUPERMARKET_REGISTRY = ConfigDict()

TIMEOUT_TIME = 10


@SCRAPERS_SUPERMARKET_REGISTRY.register(name="dia")
class DiaScrapper(ShopScrapper):
    """
    A scraper class for the DIA supermarket, inheriting from the ShopScrapper base class.

    This class handles the extraction of product data from the DIA supermarket's API,
    including product names, prices, images, and other relevant information. It supports
    fetching a list of products based on a query and computing total prices based on the
    weights or units of products from a shopping list.

    Attributes:
        market_uri (str): The API endpoint for searching products at DIA.
        image_host (str): The base URL for accessing product images.
        global_scraped_products (list): A list to store all scraped product data.

    Methods:
        get_market(): Returns the name of the market (DIA).
        get_market_uri(): Returns the market URI for product searches.
        get_product_list(response_json_obj): Extracts and returns a list of Product objects from the JSON response.
        extract_price(product_obj): Retrieves the price of a product from its JSON object.
        extract_price_unit_or_kg(product_obj): Retrieves the price per unit or kilogram of a product.
        extract_image(product_obj): Constructs the full image URL for a product.
        save_data(filename): Saves the scraped product data to a CSV file.
        print_data(): Prints the scraped product data in a formatted table.
        compute_price_with_products(weight_products=None, unit_products=None, liquid_products=None):
            Computes the total price based on the specified weight, unit, and liquid products.
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.market_uri = (
            "https://www.dia.es/api/v1/search-back/search/reduced?q={}&page=1"
        )
        self.image_host = "https://www.dia.es"
        self.global_scraped_products = []

    def get_market(self):
        """
        Returns the name of the supermarket.

        Returns:
            str: The name of the market, which is "DIA".
        """
        return "DIA"

    def get_market_uri(self):
        """
        Returns the API endpoint for product searches at the DIA supermarket.

        Returns:
            str: The market URI for searching products.
        """
        return self.market_uri

    def get_product_list(self, response_json_obj: dict) -> List[Product]:
        """
        Extracts a list of Product objects from the JSON response received from the API.

        Args:
            response_json_obj (dict): The JSON response object containing product data.

        Returns:
            List[Product]: A list of Product objects extracted from the response.
        """
        product_list = []
        products_json_list = response_json_obj.get("search_items", [])
        for product_json in products_json_list:
            product_obj = product_json
            product = Product(
                market=self.get_market(),
                brand="-",
                name=product_obj.get("display_name", ""),
                price=self.extract_price(product_obj),
                price_unit_or_kg=self.extract_price_unit_or_kg(product_obj),
                image=self.extract_image(product_obj),
            )
            product_list.append(product)

        return product_list

    def extract_price(self, product_obj: dict) -> float:
        """
        Retrieves the price of a product from its JSON object.

        Args:
            product_obj (dict): The JSON object representing the product.

        Returns:
            float: The price of the product.
        """
        prices_obj = product_obj.get("prices", {})
        return float(prices_obj.get("price", 0.0))

    def extract_price_unit_or_kg(self, product_obj: dict) -> str:
        """
        Retrieves the price per unit or kilogram of a product from its JSON object.

        Args:
            product_obj (dict): The JSON object representing the product.

        Returns:
            str: A string representing the price per unit or kilogram, or an empty string if not available.
        """
        prices_obj = product_obj.get("prices", {})
        if "price_per_unit" in prices_obj:
            price_per_unit = prices_obj.get("price_per_unit", "").replace(".", ",")
            measure_unit = prices_obj.get("measure_unit", "")
            return f"{price_per_unit} €/ {measure_unit}"
        return ""

    def extract_image(self, product_obj: dict) -> str:
        """
        Constructs the full image URL for a product from its JSON object.

        Args:
            product_obj (dict): The JSON object representing the product.

        Returns:
            str: The full URL of the product image, or an empty string if not available.
        """
        image_path = product_obj.get("image", "")
        if image_path:
            return f"{self.image_host}{image_path}"
        return ""

    def save_data(self, filename: str = "dia_scrap.csv"):
        """
        Saves the scraped product data to a CSV file.

        Args:
            filename (str): The name of the file to save the data to. Defaults to "dia_scrap.csv".
        """
        # TODO: Check if this works and also do this in every class
        full_filename = Path(self.cfg.output_folder) / filename
        if self.global_scraped_products:
            with open(full_filename, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Market", "Brand", "Name", "Price", "Image"])
                for product in self.global_scraped_products:
                    writer.writerow(
                        [
                            product.market,
                            product.brand,
                            product.name,
                            product.price,
                            product.image,
                        ]
                    )

    def print_data(self):
        """
        Prints the scraped product data in a formatted table using PrettyTable.
        """
        table = PrettyTable()
        table.field_names = [
            "Market",
            "Brand",
            "Name",
            "Price",
            "Price per Unit/Kg",
            "Image",
        ]
        for products in self.global_scraped_products:
            for product in products:
                table.add_row(
                    [
                        product.market,
                        product.brand,
                        product.name,
                        product.price,
                        product.price_unit_or_kg,
                        product.image,
                    ]
                )
        LOGGER.info(table)

    def compute_price_with_products(
        self, weight_products=None, unit_products=None, liquid_products=None
    ):
        """
        Computes the total price based on the specified weight, unit, and liquid products.

        Args:
            weight_products (dict, optional): A dictionary of products measured by weight.
            unit_products (dict, optional): A dictionary of products measured by standard units.
            liquid_products (dict, optional): A dictionary of liquid products.

        Returns:
            tuple: A tuple containing:
                - float: The total price computed from the products.
                - list: A list of scraped Product objects.
        """
        total_price = 0
        if weight_products:
            for item, quantity in weight_products.items():
                url = self.get_market_uri().format(item)
                response = requests.get(url, timeout=TIMEOUT_TIME)
                if response.status_code == 200:
                    response_json_obj = response.json()
                    products = self.get_product_list(response_json_obj)
                    chosen_product = find_closest_product(products, item)
                    if chosen_product is None:
                        LOGGER.info(
                            colorstr(
                                "cyan",
                                f"Not able to find a product similar to {item} in DIA supermarket",
                            )
                        )
                    else:
                        self.global_scraped_products.append(chosen_product)
                        total_price += compute_rough_price(quantity, chosen_product)
        if unit_products:
            for item, quantity in unit_products.items():
                url = self.get_market_uri().format(item)
                response = requests.get(url, timeout=TIMEOUT_TIME)
                if response.status_code == 200:
                    response_json_obj = response.json()
                    products = self.get_product_list(response_json_obj)
                    chosen_product = find_closest_product(products, item)
                    if chosen_product is None:
                        LOGGER.info(
                            colorstr(
                                "cyan",
                                f"Not able to find a product similar to {item} in DIA supermarket",
                            )
                        )
                    else:
                        self.global_scraped_products.append(chosen_product)
                        total_price += compute_rough_price(
                            quantity, chosen_product, unit=True
                        )
        if liquid_products:
            for item, quantity in unit_products.items():
                url = self.get_market_uri().format(item)
                response = requests.get(url, timeout=TIMEOUT_TIME)
                if response.status_code == 200:
                    response_json_obj = response.json()
                    products = self.get_product_list(response_json_obj)
                    chosen_product = find_closest_product(products, item)
                    if chosen_product is None:
                        LOGGER.info(
                            colorstr(
                                "cyan",
                                f"Not able to find a product similar to {item} in DIA supermarket",
                            )
                        )
                    else:
                        self.global_scraped_products.append(chosen_product)
                        total_price += compute_rough_price(quantity, chosen_product)
        return total_price, self.global_scraped_products


@SCRAPERS_SUPERMARKET_REGISTRY.register(name="alcampo")
class AlcampoScrapper(ShopScrapper):
    def __init__(self, cfg):
        self.cfg = cfg
        self.market_uri = "https://www.compraonline.alcampo.es/api/v5/products/search?limit=50&offset=0&sort=price&term={}"
        self.image_host = "https://www.alcampo.es"
        self.global_scraped_products = []

    def get_market(self):
        """
        Returns the name of the supermarket.

        Returns:
            str: The name of the market, which is "Alcampo".
        """
        return "Alcampo"

    def get_market_uri(self):
        """
        Returns the API endpoint for product searches at the Alcampo supermarket.

        Returns:
            str: The market URI for searching products.
        """
        return self.market_uri

    def get_product_list(self, response_json_obj: dict) -> List[Product]:
        """
        Extracts a list of Product objects from the JSON response received from the API.

        Args:
            response_json_obj (dict): The JSON response object containing product data.

        Returns:
            List[Product]: A list of Product objects extracted from the response.
        """
        product_list = []
        products_json_list = response_json_obj.get("entities", {}).get("product", {})

        for _, product_obj in products_json_list.items():
            product = Product(
                market=self.get_market(),
                brand=product_obj.get("brand", ""),
                name=product_obj.get("name", ""),
                price=self.extract_price(product_obj),
                price_unit_or_kg=self.extract_price_unit_or_kg(product_obj),
                image=self.extract_image(product_obj),
            )
            product_list.append(product)

        return product_list

    def extract_price(self, product_obj: dict) -> float:
        """
        Retrieves the current price of a product from its JSON object.

        Args:
            product_obj (dict): The JSON object representing the product.

        Returns:
            float: The price of the product.
        """
        price_info = product_obj.get("price", {}).get("current", {}).get("amount", 0.0)
        return float(price_info)

    def extract_price_unit_or_kg(self, product_obj: dict) -> str:
        """
        Retrieves the price per unit or kilogram of a product from its JSON object.

        Args:
            product_obj (dict): The JSON object representing the product.

        Returns:
            str: A string representing the price per unit or kilogram, or an empty string if not available.
        """
        price = product_obj.get("price", {}).get("unit", {})
        if price:
            label = price.get("label", "")
            label = label.split(".")[-1]
            current_price = (
                price.get("current", {}).get("amount", "0").replace(".", ",")
            )
            price_unit = f"{current_price} €/ {label}"
            price_unit = price_unit.replace("litre", "Litro").replace("each", "unidad")
            return price_unit
        return ""

    def extract_image(self, product_obj: dict) -> str:
        """
        Constructs the image URL for a product from its JSON object.

        Args:
            product_obj (dict): The JSON object representing the product.

        Returns:
            str: The URL of the product image, or an empty string if not available.
        """
        media = product_obj.get("imagePaths", [])
        if media:
            return f"{media[0]}/300x300.jpg"
        return ""

    def save_data(self, filename: str = "alcampo_scrap.csv"):
        """
        Saves the scraped product data to a CSV file.

        Args:
            filename (str): The name of the file to save the data to. Defaults to "alcampo_scrap.csv".
        """
        full_filename = Path(self.cfg.output_folder) / filename
        if self.global_scraped_products:
            with open(full_filename, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Market", "Brand", "Name", "Price", "Image"])
                for product in self.global_scraped_products:
                    writer.writerow(
                        [
                            product.market,
                            product.brand,
                            product.name,
                            product.price,
                            product.image,
                        ]
                    )

    def print_data(self):
        """
        Prints the scraped product data in a formatted table using PrettyTable.
        """
        table = PrettyTable()
        table.field_names = [
            "Market",
            "Brand",
            "Name",
            "Price",
            "Price per Unit/Kg",
            "Image",
        ]
        for product in self.global_scraped_products:
            table.add_row(
                [
                    product.market,
                    product.brand,
                    product.name,
                    product.price,
                    product.price_unit_or_kg,
                    product.image,
                ]
            )
        LOGGER.info(table)

    def compute_price_with_products(
        self, weight_products=None, unit_products=None, liquid_products=None
    ):
        """
        Computes the total price based on the specified weight, unit, and liquid products.

        Args:
            weight_products (dict, optional): A dictionary of products measured by weight.
            unit_products (dict, optional): A dictionary of products measured by standard units.
            liquid_products (dict, optional): A dictionary of liquid products.

        Returns:
            tuple: A tuple containing:
                - float: The total price computed from the products.
                - list: A list of scraped Product objects.
        """
        total_price = 0
        if weight_products:
            for item, quantity in weight_products.items():
                url = self.get_market_uri().format(item)
                response = requests.get(url, timeout=TIMEOUT_TIME)
                if response.status_code == 200:
                    response_json_obj = response.json()
                    products = self.get_product_list(response_json_obj)
                    chosen_product = find_closest_product(products, item)
                    if chosen_product is None:
                        LOGGER.info(
                            colorstr(
                                "cyan",
                                f"Not able to find a product similar to {item} in Alcampo supermarket",
                            )
                        )
                    else:
                        self.global_scraped_products.append(chosen_product)
                        total_price += compute_rough_price(quantity, chosen_product)
        if unit_products:
            for item, quantity in unit_products.items():
                url = self.get_market_uri().format(item)
                response = requests.get(url, timeout=TIMEOUT_TIME)
                if response.status_code == 200:
                    response_json_obj = response.json()
                    products = self.get_product_list(response_json_obj)
                    chosen_product = find_closest_product(products, item)
                    if chosen_product is None:
                        LOGGER.info(
                            colorstr(
                                "cyan",
                                f"Not able to find a product similar to {item} in Alcampo supermarket",
                            )
                        )
                    else:
                        self.global_scraped_products.append(chosen_product)
                        total_price += compute_rough_price(
                            quantity, chosen_product, unit=True
                        )
        if liquid_products:
            for item, quantity in unit_products.items():
                url = self.get_market_uri().format(item)
                response = requests.get(url, timeout=TIMEOUT_TIME)
                if response.status_code == 200:
                    response_json_obj = response.json()
                    products = self.get_product_list(response_json_obj)
                    chosen_product = find_closest_product(products, item)
                    if chosen_product is None:
                        LOGGER.info(
                            colorstr(
                                "cyan",
                                f"Not able to find a product similar to {item} in Alcampo supermarket",
                            )
                        )
                    else:
                        self.global_scraped_products.append(chosen_product)
                        total_price += compute_rough_price(quantity, chosen_product)
        return total_price, self.global_scraped_products


# TODO: This scrapper is wrong programmed debug
@SCRAPERS_SUPERMARKET_REGISTRY.register(name="aldi")
class AldiScrapper(ShopScrapper):
    def __init__(self, cfg):
        """
        Initializes the AldiScrapper instance with the market URI, an empty list for scraped products,
        and the image host URL.
        """
        self.cfg = cfg
        self.market_uri = (
            "https://l9knu74io7-dsn.algolia.net/1/indexes/*/queries"
            "?X-Algolia-Api-Key=19b0e28f08344395447c7bdeea32da58"
            "&X-Algolia-Application-Id=L9KNU74IO7"
        )
        self.global_scraped_products = []
        self.image_host = "https://www.aldi.es/"

    def get_market(self) -> str:
        """
        Returns the name of the supermarket market.

        Returns:
            str: The name of the market.
        """
        return "Aldi"

    def get_market_uri(self) -> str:
        """
        Returns the URI used to access the Aldi supermarket API for product search.

        Returns:
            str: The market URI.
        """
        return self.market_uri

    def get_body_post(self, term: str) -> str:
        """
        Constructs the body for the POST request to search for products in the Aldi API.

        Args:
            term (str): The search term for the product.

        Returns:
            str: The body of the POST request in JSON format.
        """
        body = {
            "requests": [
                {
                    "indexName": "prod_es_es_es_offers",
                    "params": f"clickAnalytics=true&facets=%5B%5D"
                    f"&highlightPostTag=%3C%2Fais-highlight-0000000000%3E"
                    f"&highlightPreTag=%3Cais-highlight-0000000000%3E"
                    f"&hitsPerPage=12&page=0&query={term}&tagFilters=",
                },
                {
                    "indexName": "prod_es_es_es_assortment",
                    "params": f"clickAnalytics=true&facets=%5B%5D"
                    f"&highlightPostTag=%3C%2Fais-highlight-0000000000%3E"
                    f"&highlightPreTag=%3Cais-highlight-0000000000%3E"
                    f"&hitsPerPage=12&page=0&query={term}&tagFilters=",
                },
            ]
        }
        return json.dumps(body)

    def get_http_method(self) -> str:
        """
        Returns the HTTP method used for the product search.

        Returns:
            str: The HTTP method ("POST").
        """
        return "POST"

    def get_product_list(self, response_json_obj: dict) -> List[Product]:
        """
        Extracts a list of Product objects from the JSON response from the Aldi API.

        Args:
            response_json_obj (dict): The JSON response object from the API.

        Returns:
            List[Product]: A list of Product objects.
        """
        product_list = []
        results = response_json_obj.get("results", [])

        for result in results:
            products_json_list = result.get("hits", [])

            for product_json in products_json_list:
                product_obj = product_json
                if product_obj.get("salesPrice") is not None:
                    product = Product(
                        market=self.get_market(),
                        brand="-",
                        name=product_obj.get("productName", ""),
                        price=product_obj.get("salesPrice", 0.0),
                        image=self.extract_image(product_obj),
                    )
                    product_list.append(product)
        return product_list

    def print_data(self) -> None:
        """
        Prints the scraped product data in a table format using PrettyTable.
        """
        table = PrettyTable()
        table.field_names = [
            "Market",
            "Brand",
            "Name",
            "Price",
            "Price per Unit/Kg",
            "Image",
        ]
        for product in self.global_scraped_products:
            table.add_row(
                [
                    product.market,
                    product.brand,
                    product.name,
                    product.price,
                    product.price_unit_or_kg,
                    product.image,
                ]
            )
        LOGGER.info(table)

    def compute_price_with_products(
        self,
        weight_products: Optional[dict] = None,
        unit_products: Optional[dict] = None,
        liquid_products: Optional[dict] = None,
    ) -> Tuple[float, List[Product]]:
        """
        Computes the total price by searching products and calculating their cost based on the provided quantities.

        Args:
            weight_products (Optional[dict], optional): A dictionary of weight-based products with their quantities. Defaults to None.
            unit_products (Optional[dict], optional): A dictionary of unit-based products with their quantities. Defaults to None.
            liquid_products (Optional[dict], optional): A dictionary of liquid products with their quantities. Defaults to None.

        Returns:
            Tuple[float, List[Product]]: A tuple containing the total price and the list of scraped products.
        """
        total_price = 0

        for product_dict, is_unit in [
            (weight_products, False),
            (unit_products, True),
            (liquid_products, False),
        ]:
            if product_dict:
                for item, quantity in product_dict.items():
                    market_uri = self.get_market_uri()
                    body_post = self.get_body_post(item)
                    headers = {
                        "Content-Type": "application/json",
                    }
                    response = requests.post(
                        market_uri,
                        data=body_post,
                        headers=headers,
                        timeout=TIMEOUT_TIME,
                    )
                    if response.status_code == 200:
                        response_json_obj = response.json()
                        products = self.get_product_list(response_json_obj)
                        chosen_product = find_closest_product(products, item)
                        if chosen_product is None:
                            LOGGER.info(
                                colorstr(
                                    "cyan",
                                    f"Not able to find a product similar to {item} in Aldi supermarket",
                                )
                            )
                        else:
                            self.global_scraped_products.append(chosen_product)
                            total_price += compute_rough_price(
                                quantity, chosen_product, unit=is_unit
                            )

        return total_price, self.global_scraped_products

    def save_data(self, filename: str = "aldi_scrap.csv") -> None:
        """
        Saves the scraped product data to a CSV file.

        Args:
            filename (str, optional): The name of the CSV file to save the data. Defaults to "aldi_scrap.csv".
        """

        if self.global_scraped_products:
            with open(filename, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Market", "Brand", "Name", "Price", "Image"])
                for product in self.global_scraped_products:
                    writer.writerow(
                        [
                            product.market,
                            product.brand,
                            product.name,
                            product.price,
                            product.image,
                        ]
                    )

    def extract_image(self, product_json: dict) -> str:
        """
        Extracts the image URL from a product JSON object.

        Args:
            product_json (dict): The product JSON object.

        Returns:
            str: The URL of the product image.
        """
        return product_json.get("productPicture", "")

    def extract_price(self, product_json: dict) -> float:
        """
        Extracts the price from a product JSON object.

        Args:
            product_json (dict): The product JSON object.

        Returns:
            float: The price of the product.
        """
        return float(product_json.get("salesPrice", 0.0))


@SCRAPERS_SUPERMARKET_REGISTRY.register(name="hipercor")
class HipercorScrapper(ShopScrapper):
    """
    A class to scrape product information from the Hipercor supermarket.

    This class inherits from the ShopScrapper base class and provides methods to extract product details
    from Hipercor's online API, including product name, brand, price, and image URL. It can save scraped
    data to a CSV file and print it in a formatted table.

    Attributes:
        market_uri (str): The URI for fetching product data from Hipercor.
        image_host (str): The base URL for images hosted by Hipercor.
        global_scraped_products (list): A list to store globally scraped product instances.
    """

    def __init__(self, cfg):
        """Initializes the HipercorScrapper with the necessary market URI and image host."""
        self.market_uri = (
            "https://www.hipercor.es/alimentacion/api/catalog/supermercado/type_ahead/"
            "?question={}&scope=supermarket&center=010MOH&results=10"
        )
        self.image_host = "https:"
        self.global_scraped_products = []

    def get_market(self):
        """Returns the name of the market."""
        return "Hipercor"

    def get_market_uri(self):
        """Returns the URI used to fetch product data from the market."""
        return self.market_uri

    def get_product_list(self, response_json_obj: dict) -> list:
        """
        Extracts a list of products from the JSON response object.

        Args:
            response_json_obj (dict): The JSON response object containing product data.

        Returns:
            list: A list of Product instances extracted from the JSON response.
        """
        product_list = []
        products_json_list = (
            response_json_obj.get("catalog_result", {})
            .get("products_list", {})
            .get("items", [])
        )

        for product_json in products_json_list:
            product_obj = product_json.get("product", {})
            product = Product(
                market=self.get_market(),
                brand="-",  # As the original uses "-" for the brand
                name=product_obj.get("name", ""),
                price=self.extract_price(product_obj),
                price_unit_or_kg=self.extract_price_unit_or_kg(product_obj),
                image=self.extract_image(product_obj),
            )
            product_list.append(product)

        return product_list

    def extract_price(self, product_obj: dict) -> float:
        """
        Extracts the price from a product JSON object.

        Args:
            product_obj (dict): The JSON object representing a product.

        Returns:
            float: The price of the product.
        """
        price_obj = product_obj.get("price", {})
        return price_obj.get("seo_price", 0.0)

    def extract_price_unit_or_kg(self, product_obj: dict) -> str:
        """
        Extracts the price per unit or kilogram from a product JSON object.

        Args:
            product_obj (dict): The JSON object representing a product.

        Returns:
            str: The formatted price per unit or kilogram.
        """
        price_obj = product_obj.get("price", {})
        price_unit = ""
        try:
            if price_obj.get("pum_price_only"):
                price_unit = price_obj.get("pum_price_only", "").replace("&euro; ", "€")
            elif price_obj.get("pum_price"):
                price_unit = price_obj.get("pum_price", "").replace("&euro; ", "€")
        except Exception as e:
            LOGGER.error("Hipercor get product unitPrice error %e", e)
        return price_unit

    def extract_image(self, product_obj: dict) -> str:
        """
        Extracts the image URL from a product JSON object.

        Args:
            product_obj (dict): The JSON object representing a product.

        Returns:
            str: The URL of the product image.
        """
        image_path = product_obj.get("media", {}).get("thumbnail_url", "")
        if image_path:
            image_path = image_path.replace("40x40", "325x325")
            return f"{self.image_host}{image_path}"
        return ""

    def save_data(self, filename: str = "hipercor_scrap.csv"):
        """
        Saves the scraped product data to a CSV file.

        Args:
            filename (str): The name of the file to save the data to. Defaults to 'hipercor_scrap.csv'.
        """
        if self.global_scraped_products:
            with open(filename, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Market", "Brand", "Name", "Price", "Image"])
                for product in self.global_scraped_products:
                    writer.writerow(
                        [
                            product.market,
                            product.brand,
                            product.name,
                            product.price,
                            product.image,
                        ]
                    )

    def print_data(self):
        """Prints the scraped product data in a formatted table."""
        table = PrettyTable()
        table.field_names = [
            "Market",
            "Brand",
            "Name",
            "Price",
            "Price per Unit/Kg",
            "Image",
        ]
        for product in self.global_scraped_products:
            table.add_row(
                [
                    product.market,
                    product.brand,
                    product.name,
                    product.price,
                    product.price_unit_or_kg,
                    product.image,
                ]
            )
        LOGGER.info(table)

    def compute_price_with_products(
        self, weight_products=None, unit_products=None, liquid_products=None
    ):
        """
        Computes the total price for a list of products based on their quantities.

        Args:
            weight_products (dict): A dictionary of products sold by weight.
            unit_products (dict): A dictionary of products sold by unit.
            liquid_products (dict): A dictionary of liquid products.

        Returns:
            tuple: A tuple containing the total price and a list of scraped products.
        """
        total_price = 0
        if weight_products:
            for item, quantity in weight_products.items():
                url = self.get_market_uri().format(item)
                response = requests.get(url, timeout=TIMEOUT_TIME)
                if response.status_code == 200:
                    response_json_obj = response.json()
                    products = self.get_product_list(response_json_obj)
                    chosen_product = find_closest_product(products, item)
                    if chosen_product is None:
                        LOGGER.info(
                            colorstr(
                                "cyan",
                                f"Not able to find a product similar to {item} in Hipercor supermarket",
                            )
                        )
                    else:
                        self.global_scraped_products.append(chosen_product)
                        total_price += compute_rough_price(quantity, chosen_product)
        if unit_products:
            for item, quantity in unit_products.items():
                url = self.get_market_uri().format(item)
                response = requests.get(url, timeout=TIMEOUT_TIME)
                if response.status_code == 200:
                    response_json_obj = response.json()
                    products = self.get_product_list(response_json_obj)
                    chosen_product = find_closest_product(products, item)
                    if chosen_product is None:
                        LOGGER.info(
                            colorstr(
                                "cyan",
                                f"Not able to find a product similar to {item} in Hipercor supermarket",
                            )
                        )
                    else:
                        self.global_scraped_products.append(chosen_product)
                        total_price += compute_rough_price(
                            quantity, chosen_product, unit=True
                        )
        if liquid_products:
            for item, quantity in liquid_products.items():
                url = self.get_market_uri().format(item)
                response = requests.get(url, timeout=TIMEOUT_TIME)
                if response.status_code == 200:
                    response_json_obj = response.json()
                    products = self.get_product_list(response_json_obj)
                    chosen_product = find_closest_product(products, item)
                    if chosen_product is None:
                        LOGGER.info(
                            colorstr(
                                "cyan",
                                f"Not able to find a product similar to {item} in Hipercor supermarket",
                            )
                        )
                    else:
                        self.global_scraped_products.append(chosen_product)
                        total_price += compute_rough_price(quantity, chosen_product)
        return total_price, self.global_scraped_products


@SCRAPERS_SUPERMARKET_REGISTRY.register(name="mercadona")
class MercadonaScrapper(ShopScrapper):
    def __init__(self, cfg):
        """
        Initializes the MercadonaScrapper with the market URI and an empty list for scraped products.
        """
        self.cfg = cfg
        self.market_uri = (
            "https://7uzjkl1dj0-dsn.algolia.net/1/indexes/products_prod_4315_es/query?"
            "x-algolia-application-id=7UZJKL1DJ0&x-algolia-api-key=9d8f2e39e90df472b4f2e559a116fe17"
        )
        self.global_scraped_products = []

    def get_market(self):
        """
        Retrieves the name of the market.

        Returns:
            str: The name of the market (Mercadona).
        """
        return "Mercadona"

    def get_market_uri(self):
        """
        Retrieves the market URI for making requests.

        Returns:
            str: The market URI.
        """
        return self.market_uri

    def get_body_post(self, term: str) -> dict:
        """
        Builds the body for the POST request.

        Args:
            term (str): The search term for the product.

        Returns:
            dict: The body of the POST request.
        """
        return {
            "params": f"query={term}&clickAnalytics=true&analyticsTags=%5B%22web%22%5D&getRankingInfo=true"
        }

    def get_product_list(self, response_json_obj: dict) -> List[Product]:
        """
        Extracts a list of Product objects from the JSON response.

        Args:
            response_json_obj (dict): The JSON response from the API.

        Returns:
            List[Product]: A list of Product objects extracted from the response.
        """
        product_list = []
        products_json_list = response_json_obj.get("hits", [])

        for product_obj in products_json_list:
            product = Product(
                market=self.get_market(),
                brand="-",
                name=product_obj.get("display_name", ""),
                price=self.extract_price(product_obj),
                price_unit_or_kg=self.extract_price_unit_or_kg(product_obj),
                image=self.extract_image(product_obj),
            )
            product_list.append(product)

        return product_list

    def extract_price(self, product_obj: dict) -> float:
        """
        Extracts the unit price of the product.

        Args:
            product_obj (dict): The product object from the JSON response.

        Returns:
            float: The unit price of the product.
        """
        price_info = product_obj.get("price_instructions", {}).get("unit_price", 0.0)
        return float(price_info)

    def extract_price_unit_or_kg(self, product_obj: dict) -> str:
        """
        Extracts the price per unit or kilogram.

        Args:
            product_obj (dict): The product object from the JSON response.

        Returns:
            str: The formatted price per unit or kilogram.
        """
        price_obj = product_obj.get("price_instructions", {})
        reference_price = price_obj.get("reference_price", None)
        reference_format = price_obj.get("reference_format", None)

        if reference_price and reference_format:
            formatted_price = reference_price.replace(".", ",")
            price_unit = f"{formatted_price} €/ {reference_format}"
            return price_unit
        return ""

    def extract_image(self, product_obj: dict) -> str:
        """
        Extracts the image URL for the product.

        Args:
            product_obj (dict): The product object from the JSON response.

        Returns:
            str: The image URL for the product.
        """
        image_path = product_obj.get("thumbnail", "")
        if image_path:
            return image_path
        return ""

    def save_data(self, filename: str = "mercadona_scrap.csv"):
        """
        Saves the scraped product data to a CSV file.

        Args:
            filename (str): The name of the CSV file to save the data. Defaults to "mercadona_scrap.csv".
        """
        full_filename = Path(self.cfg.output_folder) / filename
        if self.global_scraped_products:
            with open(full_filename, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Market", "Brand", "Name", "Price", "Image"])
                for product in self.global_scraped_products:
                    writer.writerow(
                        [
                            product.market,
                            product.brand,
                            product.name,
                            product.price,
                            product.image,
                        ]
                    )

    def print_data(self):
        """
        Prints the scraped product data in a table format.
        """
        table = PrettyTable()
        table.field_names = [
            "Market",
            "Brand",
            "Name",
            "Price",
            "Price per Unit/Kg",
            "Image",
        ]
        for product in self.global_scraped_products:
            table.add_row(
                [
                    product.market,
                    product.brand,
                    product.name,
                    product.price,
                    product.price_unit_or_kg,
                    product.image,
                ]
            )
        LOGGER.info(table)

    def compute_price_with_products(
        self, weight_products=None, unit_products=None, liquid_products=None
    ):
        """
        Computes the total price for a list of products based on their quantities.

        Args:
            weight_products (dict): A dictionary of products sold by weight.
            unit_products (dict): A dictionary of products sold by unit.
            liquid_products (dict): A dictionary of liquid products.

        Returns:
            tuple: A tuple containing the total price and a list of scraped products.
        """
        total_price = 0
        if weight_products:
            for item, quantity in weight_products.items():
                url = self.get_market_uri()
                response = requests.post(
                    url, json=self.get_body_post(item), timeout=TIMEOUT_TIME
                )
                if response.status_code == 200:
                    response_json_obj = response.json()
                    products = self.get_product_list(response_json_obj)
                    chosen_product = find_closest_product(products, item)
                    if chosen_product is None:
                        LOGGER.info(
                            colorstr(
                                "cyan",
                                f"Not able to find a product similar to {item} in Mercadona supermarket",
                            )
                        )
                    else:
                        self.global_scraped_products.append(chosen_product)
                        total_price += compute_rough_price(quantity, chosen_product)
        if unit_products:
            for item, quantity in unit_products.items():
                url = self.get_market_uri()
                response = requests.post(
                    url, json=self.get_body_post(item), timeout=TIMEOUT_TIME
                )
                if response.status_code == 200:
                    response_json_obj = response.json()
                    products = self.get_product_list(response_json_obj)
                    chosen_product = find_closest_product(products, item)
                    if chosen_product is None:
                        LOGGER.info(
                            colorstr(
                                "cyan",
                                f"Not able to find a product similar to {item} in Mercadona supermarket",
                            )
                        )
                    else:
                        self.global_scraped_products.append(chosen_product)
                        total_price += compute_rough_price(
                            quantity, chosen_product, unit=True
                        )
        if liquid_products:
            for item, quantity in liquid_products.items():
                url = self.get_market_uri()
                response = requests.post(
                    url, json=self.get_body_post(item), timeout=TIMEOUT_TIME
                )
                if response.status_code == 200:
                    response_json_obj = response.json()
                    products = self.get_product_list(response_json_obj)
                    chosen_product = find_closest_product(products, item)
                    if chosen_product is None:
                        LOGGER.info(
                            colorstr(
                                "cyan",
                                f"Not able to find a product similar to {item} in Mercadona supermarket",
                            )
                        )
                    else:
                        self.global_scraped_products.append(chosen_product)
                        total_price += compute_rough_price(quantity, chosen_product)
        return total_price, self.global_scraped_products


@SCRAPERS_SUPERMARKET_REGISTRY.register(name="eroski")
class EroskiScrapper(ShopScrapper):
    def __init__(self, cfg):
        self.cfg = cfg
        self.market_uri = "https://supermercado.eroski.es/es/search/results/?q={}&suggestionsFilter=false"
        self.image_host = "https://supermercado.eroski.es/images/"
        self.global_scraped_products = []

    def get_market(self) -> str:
        """
        Returns the name of the supermarket.

        Returns:
            str: The name of the supermarket ("Eroski").
        """
        return "Eroski"

    def get_market_uri(self) -> str:
        """
        Returns the market URI.

        Returns:
            str: The market URI for product search.
        """
        return self.market_uri

    def get_body_post(self, term: str) -> dict:
        """
        Constructs the request body for product search.

        Args:
            term (str): The search term for the product.

        Returns:
            dict: An empty dictionary since Eroski uses GET.
        """
        return {}

    def get_product_list(self, response_json_obj: dict) -> List[Product]:
        """
        Extracts a list of Product objects from the JSON response.

        Args:
            response_json_obj (dict): The JSON response containing product information.

        Returns:
            List[Product]: A list of Product objects.
        """
        product_list = []
        products_json_list = response_json_obj.get("list", [])
        for product_obj in products_json_list:
            product = Product(
                market=self.get_market(),
                brand=product_obj.get("brand", ""),
                name=product_obj.get("name", ""),
                price=float(product_obj.get("price", 0.0)),
                price_unit_or_kg=self.extract_price_unit_or_kg(product_obj),
                image=self.extract_image(product_obj),
            )
            product_list.append(product)

        return product_list

    def extract_price_unit_or_kg(self, product_obj: dict) -> float:
        """
        Extracts the price based on the unit or weight of the product.

        Args:
            product_obj (dict): The product object containing its details.

        Returns:
            float: The price per unit or kg.

        Raises:
            ValueError: If the weight unit is not supported.
        """
        weight_unit = product_obj["name"].split(" ")[-1]
        quantity = product_obj["name"].split(" ")[-2]
        if "x" in quantity:
            try:
                parts = quantity.split("x")
                quantity = float(parts[0]) * float(parts[1])
            except ValueError:
                LOGGER.warning(
                    "Invalid quantity format for product %s. Using 0 as quantity.",
                    product_obj["name"],
                )
                quantity = 0
        else:
            try:
                quantity = float(quantity)
            except ValueError:
                LOGGER.warning(
                    "Invalid quantity for product %s. Using 0 as quantity.",
                    product_obj["name"],
                )
                quantity = 0

        if weight_unit in ["g", "ml"]:
            return quantity / 1000 * float(product_obj["price"])
        elif weight_unit in ["kg", "L"]:
            return quantity * float(product_obj["price"])
        else:
            LOGGER.error(
                "Weight unit not supported in EroskiScrapper %s. This error is probably related to the 'scrapper' code",
                weight_unit,
            )
            return None

    def extract_image(self, product_obj: dict) -> str:
        """
        Extracts the image URL for the product.

        Args:
            product_obj (dict): The product object containing its details.

        Returns:
            str: The URL of the product image.
        """
        product_id = product_obj.get("id", "")
        if product_id:
            return f"{self.image_host}{product_id}.jpg"
        return ""

    def pre_process_response(self, response_string: str) -> dict:
        """
        Pre-processes the raw response string to extract JSON data.

        Args:
            response_string (str): The raw response string from the request.

        Returns:
            dict: A dictionary containing the processed JSON data.
        """
        start_json_pos = response_string.find("impressions")
        if start_json_pos < 0:
            return {}

        response_str = response_string[start_json_pos + len("impressions") + 3 :]
        end_json_pos = response_str.find("]")
        response_str = response_str[: end_json_pos + 1]
        response_str = response_str.replace("\\", "")

        return json.loads(f'{{"list": {response_str}}}')

    def save_data(self, filename: str = "eroski_scrap.csv"):
        """
        Saves the scraped product data to a CSV file.

        Args:
            filename (str): The name of the file to save the data to (default is "eroski_scrap.csv").
        """
        full_filename = Path(self.cfg.output_folder) / filename
        if self.global_scraped_products:
            with open(full_filename, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Market", "Brand", "Name", "Price", "Image"])
                for product in self.global_scraped_products:
                    writer.writerow(
                        [
                            product.market,
                            product.brand,
                            product.name,
                            product.price,
                            product.image,
                        ]
                    )

    def print_data(self):
        """
        Prints the scraped product data in a table format.
        """
        table = PrettyTable()
        table.field_names = ["Market", "Brand", "Name", "Price", "Image"]
        for product in self.global_scraped_products:
            table.add_row(
                [
                    product.market,
                    product.brand,
                    product.name,
                    product.price,
                    product.image,
                ]
            )
        LOGGER.info(table)

    def extract_price(self, product_obj: dict) -> float:
        """
        Extracts the price of the product.

        Args:
            product_obj (dict): The product object containing its details.

        Returns:
            float: The price of the product.
        """
        price_info = product_obj.get("price", 0.0)
        return float(price_info)

    def compute_price_with_products(
        self, weight_products=None, unit_products=None, liquid_products=None
    ) -> tuple:
        """
        Computes the total price based on the provided quantities of products.

        Args:
            weight_products (dict, optional): A dictionary of weight products and their quantities.
            unit_products (dict, optional): A dictionary of unit products and their quantities.
            liquid_products (dict, optional): A dictionary of liquid products and their quantities.

        Returns:
            tuple: A tuple containing the total price and a list of scraped products.
        """
        total_price = 0
        if weight_products:
            for item, quantity in weight_products.items():
                url = self.get_market_uri().format(item)
                response = requests.get(url, timeout=TIMEOUT_TIME)
                if response.status_code == 200:
                    response_json_obj = self.pre_process_response(response.text)
                    products = self.get_product_list(response_json_obj)
                    chosen_product = find_closest_product(products, item)
                    if chosen_product is None:
                        LOGGER.info(
                            colorstr(
                                "cyan",
                                f"Not able to find a product similar to {item} in Eroski supermarket",
                            )
                        )
                    else:
                        self.global_scraped_products.append(chosen_product)
                        total_price += compute_rough_price(quantity, chosen_product)

        if unit_products:
            for item, quantity in unit_products.items():
                url = self.get_market_uri().format(item)
                response = requests.get(url, timeout=TIMEOUT_TIME)
                if response.status_code == 200:
                    response_json_obj = self.pre_process_response(response.text)
                    products = self.get_product_list(response_json_obj)
                    chosen_product = find_closest_product(products, item)
                    if chosen_product is None:
                        LOGGER.info(
                            colorstr(
                                "cyan",
                                f"Not able to find a product similar to {item} in Eroski supermarket",
                            )
                        )
                    else:
                        self.global_scraped_products.append(chosen_product)
                        total_price += compute_rough_price(
                            quantity, chosen_product, unit=True
                        )

        if liquid_products:
            for item, quantity in liquid_products.items():
                url = self.get_market_uri().format(item)
                response = requests.get(url, timeout=TIMEOUT_TIME)
                if response.status_code == 200:
                    response_json_obj = self.pre_process_response(response.text)
                    products = self.get_product_list(response_json_obj)
                    chosen_product = find_closest_product(products, item)
                    if chosen_product is None:
                        LOGGER.info(
                            colorstr(
                                "cyan",
                                f"Not able to find a product similar to {item} in Eroski supermarket",
                            )
                        )
                    else:
                        self.global_scraped_products.append(chosen_product)
                        total_price += compute_rough_price(quantity, chosen_product)

        return total_price, self.global_scraped_products


@SCRAPERS_SUPERMARKET_REGISTRY.register(name="carrefour")
class CarrefourScrapper(ShopScrapper):
    def __init__(self, cfg):
        """
        Initializes the CarrefourScrapper instance with the market URI and an empty list for scraped products.
        """
        self.cfg = cfg
        self.market_uri: str = (
            "https://www.carrefour.es/search-api/query/v1/search?query={}&scope=desktop&lang=es&rows=24&start=0&origin=default&f.op=OR"
        )
        self.global_scraped_products: List[Product] = []

    def get_market(self) -> str:
        """
        Returns the name of the supermarket market.

        Returns:
            str: The name of the market.
        """
        return "Carrefour"

    def get_market_uri(self) -> str:
        """
        Returns the URI used to access the Carrefour supermarket API for product search.

        Returns:
            str: The market URI.
        """
        return self.market_uri

    def get_product_list(self, response_json_obj: dict) -> List[Product]:
        """
        Extracts a list of Product objects from the JSON response from the Carrefour API.

        Args:
            response_json_obj (dict): The JSON response object from the API.

        Returns:
            List[Product]: A list of Product objects.
        """
        product_list: List[Product] = []
        products_json_list = response_json_obj.get("content", {}).get("docs", [])
        LOGGER.debug(f"products_json_list: {products_json_list}")

        for product_obj in products_json_list:
            product = Product(
                market=self.get_market(),
                brand=product_obj.get("brand", "-"),
                name=product_obj.get("display_name", ""),
                price=self.extract_price(product_obj),
                price_unit_or_kg=self.extract_price_unit_or_kg(product_obj),
                image=self.extract_image(product_obj),
            )
            product_list.append(product)

        return product_list

    def extract_price(self, product_obj: dict) -> float:
        """
        Extracts the unit price of the product from the product object.

        Args:
            product_obj (dict): The product object containing pricing information.

        Returns:
            float: The unit price of the product.
        """
        return float(product_obj.get("active_price", 0.0))

    def extract_price_unit_or_kg(self, product_obj: dict) -> str:
        """
        Extracts the price per unit or kilogram from the product object.

        Args:
            product_obj (dict): The product object containing pricing information.

        Returns:
            str: The price per unit or kilogram.
        """
        price_unit_text = product_obj.get("price_per_unit_text", "")
        return price_unit_text if price_unit_text else ""

    def extract_image(self, product_obj: dict) -> str:
        """
        Extracts the image URL for the product from the product object.

        Args:
            product_obj (dict): The product object containing image information.

        Returns:
            str: The image URL for the product.
        """
        return product_obj.get("image_path", "")

    def save_data(self, filename: str = "carrefour_scrap.csv") -> None:
        """
        Saves the scraped product data to a CSV file.

        Args:
            filename (str, optional): The name of the CSV file to save the data. Defaults to "carrefour_scrap.csv".
        """
        full_filename = Path(self.cfg.output_folder) / filename
        if self.global_scraped_products:
            with open(full_filename, mode="w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["Market", "Brand", "Name", "Price", "Image"])
                for product in self.global_scraped_products:
                    writer.writerow(
                        [
                            product.market,
                            product.brand,
                            product.name,
                            product.price,
                            product.image,
                        ]
                    )

    def print_data(self) -> None:
        """
        Prints the scraped product data in a table format using PrettyTable.
        """
        table = PrettyTable()
        table.field_names = [
            "Market",
            "Brand",
            "Name",
            "Price",
            "Price per Unit/Kg",
            "Image",
        ]

        if self.global_scraped_products:
            for product in self.global_scraped_products:
                table.add_row(
                    [
                        product.market,
                        product.brand,
                        product.name,
                        product.price,
                        product.price_unit_or_kg,
                        product.image,
                    ]
                )
            LOGGER.info(table)

    def compute_price_with_products(
        self,
        weight_products: Optional[dict] = None,
        unit_products: Optional[dict] = None,
        liquid_products: Optional[dict] = None,
    ) -> Tuple[float, List[Product]]:
        """
        Computes the total price by searching products and calculating their cost based on the provided quantities.

        Args:
            weight_products (Optional[dict], optional): A dictionary of weight-based products with their quantities. Defaults to None.
            unit_products (Optional[dict], optional): A dictionary of unit-based products with their quantities. Defaults to None.
            liquid_products (Optional[dict], optional): A dictionary of liquid products with their quantities. Defaults to None.

        Returns:
            Tuple[float, List[Product]]: A tuple containing the total price and the list of scraped products.
        """
        total_price = 0

        for product_dict, is_unit in [
            (weight_products, False),
            (unit_products, True),
            (liquid_products, False),
        ]:
            if product_dict:
                for item, quantity in product_dict.items():
                    url = self.get_market_uri()
                    response = requests.post(
                        url, json=self.get_body_post(item), timeout=TIMEOUT_TIME
                    )
                    if response.status_code == 200:
                        response_json_obj = response.json()
                        products = self.get_product_list(response_json_obj)
                        chosen_product = find_closest_product(products, item)
                        if chosen_product is None:
                            LOGGER.info(
                                colorstr(
                                    "cyan",
                                    f"Not able to find a product similar to {item} in Carrefour supermarket",
                                )
                            )
                        else:
                            self.global_scraped_products.append(chosen_product)
                            total_price += compute_rough_price(
                                quantity, chosen_product, unit=is_unit
                            )

        return total_price, self.global_scraped_products

    def get_body_post(self, term: str) -> dict:
        """
        Builds the body for the POST request to search for products.

        Args:
            term (str): The search term for the product.

        Returns:
            dict: The body of the POST request containing search parameters.
        """
        return {
            "params": f"query={term}&clickAnalytics=true&analyticsTags=%5B%22web%22%5D&getRankingInfo=true"
        }
