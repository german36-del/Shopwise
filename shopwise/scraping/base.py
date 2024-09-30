from abc import ABC, abstractmethod


class ShopScrapper(ABC):
    """
    Abstract base class for scraping data from online shops.

    Attributes:
        cfg (dict): Configuration settings for the scraper.
    """

    @abstractmethod
    def __init__(self, cfg):
        """
        Initializes the ShopScrapper with configuration settings.

        Args:
            cfg (dict): Configuration settings for the scraper.
        """
        pass

    @abstractmethod
    def get_product_list(self, response_json_obj):
        """
        Extracts a list of products from a response JSON object.

        Args:
            response_json_obj (dict): A JSON object containing product data.

        Returns:
            list: A list of products extracted from the response.
        """
        pass

    @abstractmethod
    def save_data(self, filename):
        """
        Saves scraped data to a file in the specified format.

        Args:
            filename (str): The name of the file to save the data.
            file_format (str): The format in which to save the data (e.g., 'json', 'csv').
        """
        pass

    @abstractmethod
    def print_data(self):
        """
        Prints the scraped data to the console.
        """
        pass

    @abstractmethod
    def get_market(self):
        """
        Returns the name of the market from which data is being scraped.

        Returns:
            str: The name of the market.
        """
        pass

    @abstractmethod
    def get_market_uri(self):
        """
        Returns the URI of the market's webpage.

        Returns:
            str: The URI of the market's webpage.
        """
        pass

    @abstractmethod
    def extract_price(self, product_obj):
        """
        Extracts the price of a product from the product object.

        Args:
            product_obj (dict): A dictionary representing the product.

        Returns:
            float: The price of the product.
        """
        pass

    @abstractmethod
    def extract_image(self, product_obj):
        """
        Extracts the image URL of a product from the product object.

        Args:
            product_obj (dict): A dictionary representing the product.

        Returns:
            str: The URL of the product's image.
        """
        pass

    @abstractmethod
    def compute_price_with_products(
        self, weight_products, unit_products, liquid_products
    ):
        """
        Compute the rough price with respect to the products passed as arguments comparing to the
        scraping of the supermarket

        Args:
            weight_products (dict): A dictionary representing the weight product.

            unit_products (dict): A dictionary representing the unit product.

            liquid_products (dict): A dictionary representing the liquid product.

        Returns:
            float: The total price
        """
        pass
