from shopwise.scraping import SCRAPERS_REGISTRY
from shopwise.utils import DEFAULT_CFG, LOGGER, ConfigDict, colorstr
from shopwise.utils.supermarket import process_shoping_list
import torch
import os
from transformers import AutoImageProcessor, AutoModel


class ShopWise:
    """
    A class to manage the process of scraping prices from multiple supermarkets and
    determining the optimal supermarket for a given shopping list.

    Attributes:
        supermarkets (list): A list of supermarkets to scrape data from.
        cfg (ConfigDict): Configuration settings for the scraping process.
        scrapers (dict): A dictionary mapping supermarkets to their corresponding scraper instances.
        products (dict): A dictionary to hold product data.

    Methods:
        compute_optimal_supermarket():
            Computes the optimal supermarket based on prices for the products in the shopping list.
    """

    def __init__(self, task, **kwargs):
        """
        Initializes the ShopWise instance with specified task and configuration.

        Args:
            task (str): The task type for which scrapers will be registered.
            **kwargs: Additional keyword arguments for configuration, including:
                - supermarkets (str): A space-separated list of supermarkets to scrape.
                - Any other configuration options to be merged with DEFAULT_CFG.

        Raises:
            ValueError: If the specified task does not have corresponding scrapers registered.
        """
        self.supermarkets = kwargs.get("supermarkets", None).split(" ")
        self.cfg = ConfigDict({**DEFAULT_CFG, **kwargs})
        self.scrapers = {}
        self.products = {}
        # If added more registries it should be placed somewhere else
        for supermarket in self.supermarkets:
            self.scrapers[supermarket] = SCRAPERS_REGISTRY.get(task).get(supermarket)(
                self.cfg
            )
        self.task_map[task][self.cfg.shop_task]()

    def compute_optimal_supermarket(self):
        """
        Computes the optimal supermarket based on the prices of products in the shopping list.

        The method processes the shopping list to categorize products into weight, unit,
        and liquid types. It then calculates the total prices for each supermarket,
        optionally printing and saving the scraped data. The optimal supermarket is determined
        as the one with the lowest total price for the available products.

        If valid supermarkets are found, logs the optimal supermarket; otherwise, logs a warning
        indicating no valid supermarkets were found.

        Returns:
            None
        """
        weight_products, unit_products, liquid_products = process_shoping_list(
            self.cfg.shoplist_path
        )
        supermarket_prices = {}
        for supermarket, scraper in self.scrapers.items():
            supermarket_prices[supermarket] = scraper.compute_price_with_products(
                weight_products, unit_products, liquid_products
            )
            if self.cfg.show:
                scraper.print_data()
            if self.cfg.save_scrap:
                scraper.save_data()
        filtered_supermarket_prices = {
            supermarket: price_and_products
            for supermarket, price_and_products in supermarket_prices.items()
            if len(price_and_products[1]) > 0
        }
        if filtered_supermarket_prices:
            optimal_supermarket = min(
                filtered_supermarket_prices, key=filtered_supermarket_prices.get
            )
            LOGGER.info(
                colorstr(
                    "cyan",
                    f"The optimal supermarket for your shopping is {optimal_supermarket}",
                )
            )
        else:
            LOGGER.warning(
                colorstr(
                    "yellow",
                    "No supermarkets found with valid prices for your shopping list.",
                )
            )

    def search_similar_products(self):
        similar_products = {}
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        processor = AutoImageProcessor.from_pretrained("facebook/dinov2-small")
        model = AutoModel.from_pretrained("facebook/dinov2-small").to(device)
        items_file_mapper = self.cfg.example_images_folder + "/items.txt"
        if os.path.exists(items_file_mapper):
            with open(items_file_mapper, "r") as file:
                for line in file:
                    words = line.strip().split()
                    if len(words) > 0:
                        image_path = words[0]
                        items = " ".join(words[1:])
                        for supermarket, scraper in self.scrapers.items():
                            similar_products[supermarket] = (
                                scraper.get_most_similar_product(
                                    image_path, processor, model, device, items
                                )
                            )
        else:
            raise FileNotFoundError(
                f"There must be a file with a name for the items you want to search in similarity search like {self.cfg.example_images_folder}/items.txt"
            )

    @property
    def task_map(self):
        """
        Defines the tasks to be performed by the task map.

        This function creates a mapping of task names to their respective methods,
        enabling structured execution of specified tasks within the class.

        Returns:
            dict: A dictionary mapping task names (str) to corresponding methods (callable).
        """
        return {
            "supermarket": {
                "optimal_shop": self.compute_optimal_supermarket,
                "similar_product": self.search_similar_products,
            },
        }
