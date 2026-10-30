from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4


class Product:
    def __init__(self, SKU, Name, Category, Unit_Cost, Selling_Price, Stock, Reorder_Level, Image=""):
        self.SKU = str(SKU).strip()
        self.Name = str(Name).strip()
        self.Category = str(Category).strip()
        self.Unit_Cost = self._validate_price(Unit_Cost, "Unit cost")
        self.Selling_Price = self._validate_price(Selling_Price, "Selling price")
        self.Stock = self._validate_whole_number(Stock, "Stock")
        self.Reorder_Level = self._validate_whole_number(Reorder_Level, "Reorder level")
        self.Image = str(Image).strip()
        self.Active = True

        if not self.SKU:
            raise ValueError("SKU cannot be empty")
        if not self.Name:
            raise ValueError("Product name cannot be empty")
        if not self.Category:
            raise ValueError("Category cannot be empty")

    @staticmethod
    def _validate_price(value, field_name):
        try:
            value = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{field_name} must be a valid number")
        if value < 0 or value in (float("inf"), float("-inf")) or value != value:
            raise ValueError(f"{field_name} must be finite and non-negative")
        return value

    @staticmethod
    def _validate_whole_number(value, field_name):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError(f"{field_name} must be a non-negative whole number")
        return value

    def search_product(self, name):
        search_text = str(name).strip().lower()
        return bool(search_text) and search_text in self.Name.lower()

    def add_stock(self, quantity):
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise ValueError("Restock quantity must be a positive whole number")
        self.Stock += quantity
        return self.Stock

    def remove_stock(self, quantity):
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise ValueError("Quantity must be a positive whole number")
        if self.Stock < quantity:
            return False
        self.Stock -= quantity
        return True

    def get_stock_status(self):
        if self.Stock <= self.Reorder_Level:
            return "You need to restock this product"
        return "Stock is sufficient"


class CartItem:
    def __init__(self, product, quantity):
        if not isinstance(product, Product):
            raise TypeError("Cart item must refer to a Product")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise ValueError("Quantity must be a positive whole number")
        self.product = product
        self.quantity = quantity

    def get_subtotal(self):
        return self.product.Selling_Price * self.quantity

    def increase_quantity(self, quantity):
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise ValueError("Quantity must be a positive whole number")
        self.quantity += quantity

    def decrease_quantity(self, quantity):
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise ValueError("Quantity must be a positive whole number")
        if self.quantity < quantity:
            return False
        self.quantity -= quantity
        return True


class Cart:
    def __init__(self):
        self.items = []

    def add_item(self, product, quantity):
        if not isinstance(product, Product):
            raise TypeError("Cart item must refer to a Product")
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise ValueError("Quantity must be a positive whole number")

        existing_item = next(
            (item for item in self.items if item.product.SKU == product.SKU), None
        )
        current_quantity = existing_item.quantity if existing_item else 0
        if current_quantity + quantity > product.Stock:
            raise ValueError("Not enough stock for this quantity")

        if existing_item:
            existing_item.increase_quantity(quantity)
        else:
            self.items.append(CartItem(product, quantity))
        # Stock is reserved only when checkout succeeds, not when adding to cart.
        return self.calculate_subtotal()

    def remove_item(self, product_SKU, quantity):
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise ValueError("Quantity must be a positive whole number")
        for item in self.items:
            if item.product.SKU == str(product_SKU).strip():
                if not item.decrease_quantity(quantity):
                    return False
                if item.quantity == 0:
                    self.items.remove(item)
                # Removing from the cart does not change inventory.
                return True
        return False

    def is_empty(self):
        return len(self.items) == 0

    def calculate_subtotal(self):
        return sum(item.get_subtotal() for item in self.items)

    def clear_cart(self):
        self.items.clear()


class Order:
    def __init__(self, cart, discount_percent=0):
        if cart.is_empty():
            raise ValueError("Cannot create an order from an empty cart")
        if isinstance(discount_percent, bool) or not isinstance(discount_percent, (int, float)):
            raise ValueError("Discount must be a number from 0 to 100")
        if not 0 <= discount_percent <= 100:
            raise ValueError("Discount must be from 0 to 100")

        self.sale_id = str(uuid4())
        self.timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        # Keep sale-time values so later product edits do not change this order.
        self.items = [
            {
                "sku": item.product.SKU,
                "name": item.product.Name,
                "quantity": item.quantity,
                "unit_selling_price": item.product.Selling_Price,
                "unit_cost": item.product.Unit_Cost,
                "subtotal": item.product.Selling_Price * item.quantity,
                "cost": item.product.Unit_Cost * item.quantity,
            }
            for item in cart.items
        ]
        self.subtotal = sum(item["subtotal"] for item in self.items)
        self.total_cost = sum(item["cost"] for item in self.items)
        self.discount_percent = float(discount_percent)
        self.discount_amount = self.subtotal * self.discount_percent / 100
        self.final_total = self.subtotal - self.discount_amount
        self.gross_profit = self.final_total - self.total_cost
        self.payment_method = ""
        self.received_amount = 0.0
        self.change = 0.0

    def calculate_final_total(self):
        self.discount_amount = self.subtotal * self.discount_percent / 100
        self.final_total = self.subtotal - self.discount_amount
        self.gross_profit = self.final_total - self.total_cost
        return self.final_total

    def set_payment_method(self, payment_method):
        self.payment_method = str(payment_method).strip()

    def process_cash(self, received_amount):
        try:
            received_amount = float(received_amount)
        except (TypeError, ValueError):
            raise ValueError("Received amount must be a valid number")
        if received_amount < 0 or received_amount != received_amount:
            raise ValueError("Received amount must be finite and non-negative")
        self.received_amount = received_amount
        if self.received_amount >= self.final_total:
            self.change = round(self.received_amount - self.final_total, 2)
            return True
        self.change = 0.0
        return False


class ShopPilotManagementSystem:
    def __init__(self, shop_name="ShopPilot"):
        self.shop_name = str(shop_name).strip() or "ShopPilot"
        self.products = {}  # SKU -> Product
        self.cart = Cart()
        self.orders = []

    def add_product(self, product):
        if not isinstance(product, Product):
            raise TypeError("product must be a Product object")
        if product.SKU in self.products:
            raise ValueError(f"A product with SKU {product.SKU} already exists")
        self.products[product.SKU] = product
        return product

    def get_product(self, sku):
        sku = str(sku).strip()
        if sku not in self.products:
            raise ValueError(f"Product not found: {sku}")
        return self.products[sku]

    def search_products(self, search_text):
        search_text = str(search_text).strip().lower()
        if not search_text:
            return []
        return [p for p in self.products.values()
                if search_text in p.SKU.lower() or p.search_product(search_text)]

    def update_product(self, sku, **changes):
        product = self.get_product(sku)
        allowed = {"Name", "Category", "Unit_Cost", "Selling_Price",
                   "Stock", "Reorder_Level", "Active"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"Unknown product fields: {', '.join(sorted(unknown))}")

        # Validate all proposed values before changing the product.
        validated = {}
        for field, value in changes.items():
            if field in ("Name", "Category"):
                value = str(value).strip()
                if not value:
                    raise ValueError(f"{field} cannot be empty")
            elif field in ("Unit_Cost", "Selling_Price"):
                value = Product._validate_price(value, field.replace("_", " "))
            elif field in ("Stock", "Reorder_Level"):
                value = Product._validate_whole_number(value, field.replace("_", " "))
            elif field == "Active" and not isinstance(value, bool):
                raise ValueError("Active must be True or False")
            validated[field] = value
        for field, value in validated.items():
            setattr(product, field, value)
        return product

    def deactivate_product(self, sku):
        return self.update_product(sku, Active=False)

    def restock_product(self, sku, quantity):
        return self.get_product(sku).add_stock(quantity)

    def get_low_stock_products(self):
        return [p for p in self.products.values()
                if p.Active and p.Stock <= p.Reorder_Level]

    def add_to_cart(self, sku, quantity):
        product = self.get_product(sku)
        if not product.Active:
            raise ValueError(f"{product.Name} is inactive")
        # Cart validates quantity and available stock.
        return self.cart.add_item(product, quantity)

    def remove_from_cart(self, sku, quantity):
        if not self.cart.remove_item(sku, quantity):
            raise ValueError("Product is not in the cart, or quantity is too large")
        return self.cart.calculate_subtotal()

    def cancel_cart(self):
        self.cart.clear_cart()

    def checkout(self, discount_percent=0, payment_method="", received_amount=None):
        if self.cart.is_empty():
            raise ValueError("Cannot checkout an empty cart")
        # Validate all lines before changing any stock.
        for item in self.cart.items:
            if not item.product.Active:
                raise ValueError(f"{item.product.Name} is inactive")
            if item.quantity > item.product.Stock:
                raise ValueError(f"Not enough stock for {item.product.Name}")

        order = Order(self.cart, discount_percent)
        if payment_method:
            order.set_payment_method(payment_method)
        if received_amount is not None and not order.process_cash(received_amount):
            raise ValueError("Cash received is less than the order total")

        original_stock = {item.product.SKU: item.product.Stock for item in self.cart.items}
        try:
            for item in self.cart.items:
                if not item.product.remove_stock(item.quantity):
                    raise ValueError(f"Not enough stock for {item.product.Name}")
        except Exception:
            for item in self.cart.items:
                item.product.Stock = original_stock[item.product.SKU]
            raise

        self.orders.append(order)
        self.cart.clear_cart()
        return order

    def format_receipt(self, order):
        if order not in self.orders:
            raise ValueError("Order does not belong to this shop")
        sale_time = datetime.fromisoformat(order.timestamp).astimezone()
        lines = [self.shop_name, f"Sale ID: {order.sale_id}",
                 f"Date / time: {sale_time.strftime('%d/%m/%Y, %H:%M:%S')}", "-" * 44]
        for item in order.items:
            final_line_total = item["subtotal"] * (1 - order.discount_percent / 100)
            lines.append(
                f"{item['name']} x {item['quantity']}"
                f" \t— EGP {final_line_total:.2f}"
            )
        lines.extend([
            "-" * 44,
            f"Subtotal: EGP {order.subtotal:.2f}",
            f"Discount ({order.discount_percent:.2f}%): -EGP {order.discount_amount:.2f}",
            f"Total: EGP {order.final_total:.2f}",
        ])
        if order.payment_method:
            lines.append(f"Payment method: {order.payment_method}")
        if order.received_amount:
            lines.extend([f"Cash received: EGP {order.received_amount:.2f}",
                          f"Change: EGP {order.change:.2f}"])
        return "\n".join(lines)

    def save_inventory(self, file_path):
        path = Path(file_path)
        data = {
            "products": [
                {"SKU": p.SKU, "Name": p.Name, "Category": p.Category,
                 "Unit cost": p.Unit_Cost, "Selling price": p.Selling_Price,
                 "Stock": p.Stock, "Reorder level": p.Reorder_Level,
                 "Image": p.Image, "Active": p.Active}
                for p in self.products.values()
            ],
        }
        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2, allow_nan=False)
        return path

    def load_inventory(self, file_path, replace=True):
        if not self.cart.is_empty():
            raise ValueError("Cannot load inventory while the cart contains items")
        with Path(file_path).open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict) or not isinstance(data.get("products"), list):
            raise ValueError("Inventory JSON must contain a products list")

        # Build and validate the full file before changing live inventory.
        loaded = {}
        for record in data["products"]:
            if not isinstance(record, dict):
                raise ValueError("Each product entry must be a JSON object")
            product = Product(
                SKU=record.get("SKU"), Name=record.get("Name"),
                Category=record.get("Category"),
                Unit_Cost=record.get("Unit cost", record.get("Unit_Cost")),
                Selling_Price=record.get("Selling price", record.get("Selling_Price")),
                Stock=record.get("Stock"),
                Reorder_Level=record.get("Reorder level", record.get("Reorder_Level")),
                Image=record.get("Image", ""),
            )
            if product.SKU in loaded:
                raise ValueError(f"Duplicate SKU in inventory file: {product.SKU}")
            product.Active = record.get("Active", True)
            if not isinstance(product.Active, bool):
                raise ValueError(f"Active must be True or False for SKU {product.SKU}")
            loaded[product.SKU] = product

        if replace:
            self.products = loaded
        else:
            duplicates = set(self.products) & set(loaded)
            if duplicates:
                raise ValueError(f"Inventory already contains SKU: {sorted(duplicates)[0]}")
            self.products.update(loaded)
        self.shop_name = str(data.get("shop_name", self.shop_name)).strip() or self.shop_name
        return len(loaded)
