import json
import re
import shutil
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from PIL import Image as PILImage, ImageOps, ImageTk

from ShopPilot_system import Product, ShopPilotManagementSystem


class ShopPilotApp:
    NAVY = "#0A1931"
    PALE_BLUE = "#B3CFE5"
    STEEL_BLUE = "#4A7FA7"
    MID_BLUE = "#1A3D63"
    BG = "#F6FAFD"
    TEXT = NAVY
    MUTED = MID_BLUE
    LOW_STOCK_BG = "#FFF1CC"
    OUT_OF_STOCK_BG = "#FDE2E2"

    def __init__(self, root):
        self.root = root
        self.root.title("ShopPilot | Shop Manager")
        self.root.geometry("1180x740")
        self.root.minsize(960, 620)
        self.root.configure(bg=self.BG)

        project_dir = Path(__file__).resolve().parent
        self.inventory_path = project_dir / "data" / "products.json"
        self.sales_path = project_dir / "data" / "sales.json"
        self.product_image_dir = project_dir / "product_photo"
        self.product_images = {}
        self.preview_photo = None
        self.preview_image_path = None
        self.shop = ShopPilotManagementSystem("ShopPilot")
        self.startup_error = None
        if self.inventory_path.exists():
            try:
                self.shop.load_inventory(self.inventory_path)
            except (OSError, ValueError, TypeError) as exc:
                self.startup_error = str(exc)

        self.search_var = tk.StringVar()
        self.category_filter_var = tk.StringVar(value="All")
        self.discount_var = tk.StringVar(value="0")
        self._configure_style()
        self._build_layout()
        self.refresh_all()

        if self.startup_error:
            self.root.after(
                200,
                lambda: messagebox.showerror(
                    "Inventory could not be loaded",
                    f"The inventory file was not loaded. The app opened with an empty inventory.\n\n{self.startup_error}",
                    parent=self.root,
                ),
            )

    def _configure_style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TFrame", background=self.BG)
        style.configure("Card.TFrame", background=self.PALE_BLUE)
        style.configure("TLabel", background=self.BG, foreground=self.TEXT, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=self.NAVY, foreground="white", font=("Segoe UI", 22, "bold"))
        style.configure("Subtitle.TLabel", background=self.NAVY, foreground="#c7d8e9", font=("Segoe UI", 10))
        style.configure("Section.TLabel", background=self.PALE_BLUE, foreground=self.TEXT, font=("Segoe UI", 13, "bold"))
        style.configure("Muted.TLabel", background=self.PALE_BLUE, foreground=self.MUTED, font=("Segoe UI", 9))
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8))
        style.configure("Accent.TButton", background=self.MID_BLUE, foreground=self.BG, borderwidth=0)
        style.map("Accent.TButton", background=[("active", self.STEEL_BLUE)])
        style.configure("Treeview", rowheight=44, font=("Segoe UI", 9), background=self.BG, fieldbackground=self.BG)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background=self.PALE_BLUE, foreground=self.NAVY)

    def _build_layout(self):
        header = tk.Frame(self.root, bg=self.NAVY, height=90)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="ShopPilot", bg=self.NAVY, fg="white",
                 font=("Segoe UI", 23, "bold")).pack(anchor="w", padx=24, pady=(15, 0))
        tk.Label(header, text="Inventory, cart and checkout", bg=self.NAVY, fg=self.PALE_BLUE,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=26, pady=(0, 12))

        toolbar = ttk.Frame(self.root, padding=(20, 14))
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Search products").pack(side="left", padx=(0, 8))
        search = ttk.Entry(toolbar, textvariable=self.search_var, width=32)
        search.pack(side="left", ipady=5)
        search.bind("<KeyRelease>", lambda _event: self.refresh_inventory())
        ttk.Button(toolbar, text="Add product", style="Accent.TButton",
                   command=self.add_product_dialog).pack(side="right", padx=(8, 0))
        ttk.Button(toolbar, text="Edit selected", command=self.edit_product_dialog).pack(side="right", padx=8)
        ttk.Button(toolbar, text="Restock selected", command=self.restock_selected).pack(side="right")
        ttk.Button(toolbar, text="Analysis", style="Accent.TButton",
                   command=self.open_analysis).pack(side="right", padx=(0, 8))

        body = ttk.Frame(self.root, padding=(20, 0, 20, 14))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        inventory_card = ttk.Frame(body, style="Card.TFrame", padding=14)
        inventory_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        inventory_card.rowconfigure(1, weight=1)
        inventory_card.columnconfigure(0, weight=1)
        inventory_card.columnconfigure(1, weight=0)
        inventory_header = ttk.Frame(inventory_card, style="Card.TFrame")
        inventory_header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        inventory_header.columnconfigure(1, weight=1)
        ttk.Label(inventory_header, text="Inventory", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(inventory_header, text="Category:", style="Muted.TLabel").grid(row=0, column=2, padx=(8, 5))
        self.category_filter_combo = ttk.Combobox(
            inventory_header, textvariable=self.category_filter_var,
            state="readonly", width=18,
        )
        self.category_filter_combo.grid(row=0, column=3, sticky="e")
        self.category_filter_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_inventory())

        inventory_columns = ("sku", "name", "category", "price", "stock", "status")
        self.inventory_tree = ttk.Treeview(inventory_card, columns=inventory_columns, show="tree headings", selectmode="browse")
        self.inventory_tree.heading("#0", text="")
        self.inventory_tree.column("#0", width=56, minwidth=56, stretch=False, anchor="w")
        headings = {"sku": "SKU", "name": "Product", "category": "Category",
                    "price": "Price (EGP)", "stock": "Stock", "status": "Status"}
        widths = {"sku": 72, "name": 145, "category": 105, "price": 85, "stock": 55, "status": 90}
        for col in inventory_columns:
            self.inventory_tree.heading(col, text=headings[col])
            self.inventory_tree.column(col, width=widths[col], anchor="w" if col in ("sku", "name", "category", "status") else "center")
        self.inventory_tree.grid(row=1, column=0, sticky="nsew")
        inventory_scroll = ttk.Scrollbar(inventory_card, orient="vertical", command=self.inventory_tree.yview)
        inventory_scroll.grid(row=1, column=1, sticky="ns")
        self.inventory_tree.configure(yscrollcommand=inventory_scroll.set)
        self.inventory_tree.bind("<Double-1>", lambda _event: self.add_selected_to_cart())
        self.inventory_tree.bind("<Button-1>", self._handle_inventory_click, add="+")
        self.inventory_tree.bind("<<TreeviewSelect>>", lambda _event: self.show_selected_product_preview())
        self.inventory_tree.tag_configure("low_stock", background=self.LOW_STOCK_BG, foreground=self.NAVY)
        self.inventory_tree.tag_configure("out_of_stock", background=self.OUT_OF_STOCK_BG, foreground=self.NAVY)
        self.inventory_tree.tag_configure("inactive", background=self.PALE_BLUE, foreground=self.MID_BLUE)

        inventory_actions = ttk.Frame(inventory_card, style="Card.TFrame")
        inventory_actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(inventory_actions, text="Add selected to cart", style="Accent.TButton",
                   command=self.add_selected_to_cart).pack(side="left")
        ttk.Button(inventory_actions, text="Deactivate selected", command=self.deactivate_selected).pack(side="left", padx=8)
        self.stock_summary = ttk.Label(inventory_actions, text="", style="Muted.TLabel")
        self.stock_summary.pack(side="right")

        self.preview_card = tk.Frame(inventory_card, bg=self.BG, padx=10, pady=6,
                                     highlightthickness=1, highlightbackground=self.PALE_BLUE)
        self.preview_card.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        self.preview_card.columnconfigure(1, weight=1)
        self.preview_image_label = tk.Label(self.preview_card, text="", bg=self.BG, width=12, height=6,
                                            cursor="hand2")
        self.preview_image_label.grid(row=0, column=0, rowspan=2, padx=(2, 12))
        self.preview_image_label.bind("<Button-1>", lambda _event: self._open_product_image())
        self.preview_name_label = tk.Label(self.preview_card, text="Select a product to preview",
                                           bg=self.BG, fg=self.NAVY,
                                           font=("Segoe UI", 12, "bold"), anchor="w")
        self.preview_name_label.grid(row=0, column=1, sticky="sw")
        self.preview_hint_label = tk.Label(self.preview_card, text="Click the image to enlarge it",
                                           bg=self.BG, fg=self.MID_BLUE,
                                           font=("Segoe UI", 9), anchor="w")
        self.preview_hint_label.grid(row=1, column=1, sticky="nw")

        cart_card = ttk.Frame(body, style="Card.TFrame", padding=14)
        cart_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        cart_card.rowconfigure(1, weight=1)
        cart_card.columnconfigure(0, weight=1)
        ttk.Label(cart_card, text="Shopping cart", style="Section.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 10))

        cart_columns = ("sku", "name", "qty", "unit", "total")
        self.cart_tree = ttk.Treeview(cart_card, columns=cart_columns, show="headings", selectmode="browse")
        cart_headings = {"sku": "SKU", "name": "Product", "qty": "Qty", "unit": "Each", "total": "Total"}
        cart_widths = {"sku": 62, "name": 115, "qty": 42, "unit": 70, "total": 75}
        for col in cart_columns:
            self.cart_tree.heading(col, text=cart_headings[col])
            self.cart_tree.column(col, width=cart_widths[col], anchor="w" if col in ("sku", "name") else "center")
        self.cart_tree.grid(row=1, column=0, sticky="nsew")
        cart_scroll = ttk.Scrollbar(cart_card, orient="vertical", command=self.cart_tree.yview)
        cart_scroll.grid(row=1, column=1, sticky="ns")
        self.cart_tree.configure(yscrollcommand=cart_scroll.set)

        cart_actions = ttk.Frame(cart_card, style="Card.TFrame")
        cart_actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(cart_actions, text="Remove quantity", command=self.remove_cart_quantity).pack(side="left")
        ttk.Button(cart_actions, text="Clear cart", command=self.clear_cart).pack(side="left", padx=8)

        checkout_box = ttk.Frame(cart_card, style="Card.TFrame")
        checkout_box.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        ttk.Label(checkout_box, text="Discount %").grid(row=0, column=0, sticky="w")
        ttk.Entry(checkout_box, textvariable=self.discount_var, width=9).grid(row=0, column=1, sticky="w", padx=8)
        self.subtotal_label = ttk.Label(checkout_box, text="Subtotal: EGP 0.00", style="Section.TLabel")
        self.subtotal_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Button(checkout_box, text="Checkout", style="Accent.TButton",
                   command=self.checkout).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))

        footer = ttk.Frame(self.root, padding=(20, 0, 20, 12))
        footer.pack(fill="x")
        ttk.Label(footer, text=f"Inventory file: {self.inventory_path}", style="Muted.TLabel").pack(side="left")
        ttk.Button(footer, text="Save inventory", command=self.save_inventory).pack(side="right")

    def refresh_all(self):
        self.refresh_inventory()
        self.refresh_cart()

    def refresh_inventory(self):
        query = self.search_var.get().strip().lower()
        categories = sorted({p.Category for p in self.shop.products.values()})
        category_options = ["All", *categories]
        self.category_filter_combo.configure(values=category_options)
        selected_category = self.category_filter_var.get()
        if selected_category not in category_options:
            self.category_filter_var.set("All")
            selected_category = "All"
        previous_selection = self.inventory_tree.selection()
        previous_sku = previous_selection[0] if previous_selection else None
        for row in self.inventory_tree.get_children():
            self.inventory_tree.delete(row)
        visible = [p for p in self.shop.products.values()
                   if (query in p.SKU.lower() or p.search_product(query))
                   and (selected_category == "All" or p.Category == selected_category)]
        for product in visible:
            status = "Inactive" if not product.Active else (
                "Low stock" if product.Stock <= product.Reorder_Level else "In stock"
            )
            row_tag = "out_of_stock" if product.Stock == 0 else (
                "inactive" if not product.Active else
                "low_stock" if product.Stock <= product.Reorder_Level else ""
            )
            self.inventory_tree.insert(
                "", "end", iid=product.SKU, image=self._load_product_image(product),
                values=(product.SKU, product.Name, product.Category,
                        f"{product.Selling_Price:.2f}", product.Stock, status),
                tags=(row_tag,) if row_tag else (),
            )
        if visible:
            selection = previous_sku if previous_sku in self.inventory_tree.get_children() else visible[0].SKU
            self.inventory_tree.selection_set(selection)
            self.inventory_tree.focus(selection)
        else:
            self.preview_image_path = None
            self.preview_photo = None
            self.preview_image_label.configure(image="", text="No product selected")
            self.preview_name_label.configure(text="No matching product")
            self.preview_hint_label.configure(text="Try another search")
        low_count = len(self.shop.get_low_stock_products())
        self.stock_summary.configure(text=f"{len(self.shop.products)} products  ·  {low_count} low stock")
        if visible:
            self.show_selected_product_preview()

    def _load_product_image(self, product, max_size=34):
        image_path = self._resolve_product_image_path(product)
        if image_path is None or not image_path.is_file():
            return ""

        cache_key = (str(image_path.resolve()), max_size)
        if cache_key not in self.product_images:
            try:
                with PILImage.open(cache_key[0]) as source:
                    image = ImageOps.exif_transpose(source).convert("RGBA")
                    image.thumbnail((max_size, max_size), PILImage.Resampling.LANCZOS)
                    self.product_images[cache_key] = ImageTk.PhotoImage(image, master=self.root)
            except (OSError, ValueError):
                return ""
        return self.product_images[cache_key]

    def _resolve_product_image_path(self, product):
        image_name = Path(product.Image).name if product.Image else ""
        image_path = self.product_image_dir / image_name if image_name else None
        # These supplied photo names differ from the labels in products.json.
        fallback_names = {"P003": "wire-mouse.png", "P004": "Wireless_Mouse.png"}
        if (image_path is None or not image_path.is_file()) and product.SKU in fallback_names:
            image_path = self.product_image_dir / fallback_names[product.SKU]
        return image_path if image_path and image_path.is_file() else None

    def show_selected_product_preview(self):
        selection = self.inventory_tree.selection()
        if not selection:
            return
        try:
            product = self.shop.get_product(selection[0])
        except ValueError:
            return
        self.preview_name_label.configure(text=f"{product.Name}  ·  {product.SKU}")
        self.preview_image_path = self._resolve_product_image_path(product)
        image = self._load_product_image(product, max_size=88)
        if image:
            self.preview_photo = image
            self.preview_image_label.configure(image=image, text="")
            self.preview_hint_label.configure(text="Click the image to view it larger")
        else:
            self.preview_photo = None
            self.preview_image_path = None
            self.preview_image_label.configure(image="", text="Image unavailable", fg=self.MID_BLUE)
            self.preview_hint_label.configure(text="Check the product photo file")

    def _open_product_image(self):
        if not self.preview_image_path:
            return
        try:
            with PILImage.open(self.preview_image_path) as source:
                image = ImageOps.exif_transpose(source).convert("RGBA")
                image.thumbnail((640, 640), PILImage.Resampling.LANCZOS)
                image = ImageTk.PhotoImage(image, master=self.root)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Image could not be opened", str(exc), parent=self.root)
            return

        window = tk.Toplevel(self.root)
        window.title("Product image")
        window.configure(bg=self.NAVY)
        window.transient(self.root)
        label = tk.Label(window, image=image, bg=self.NAVY, padx=16, pady=16)
        label.pack()
        window._product_image_reference = image
        ttk.Button(window, text="Close", command=window.destroy).pack(pady=(0, 12))

    def _handle_inventory_click(self, event):
        if self.inventory_tree.identify_column(event.x) != "#0":
            return
        sku = self.inventory_tree.identify_row(event.y)
        if not sku:
            return
        self.root.after(100, lambda selected_sku=sku: self._open_product_image_for_sku(selected_sku))

    def _open_product_image_for_sku(self, sku):
        try:
            product = self.shop.get_product(sku)
        except ValueError:
            return
        self.preview_image_path = self._resolve_product_image_path(product)
        self._open_product_image()

    def refresh_cart(self):
        for row in self.cart_tree.get_children():
            self.cart_tree.delete(row)
        for item in self.shop.cart.items:
            self.cart_tree.insert(
                "", "end", iid=item.product.SKU,
                values=(item.product.SKU, item.product.Name, item.quantity,
                        f"{item.product.Selling_Price:.2f}", f"{item.get_subtotal():.2f}"),
            )
        self.subtotal_label.configure(text=f"Subtotal: EGP {self.shop.cart.calculate_subtotal():.2f}")

    def _selected_sku(self, tree):
        selection = tree.selection()
        if not selection:
            messagebox.showinfo("Select a product", "Select a product first.", parent=self.root)
            return None
        return selection[0]

    def add_selected_to_cart(self):
        sku = self._selected_sku(self.inventory_tree)
        if sku is None:
            return
        quantity = simpledialog.askinteger("Add to cart", "Quantity:", minvalue=1, parent=self.root)
        if quantity is None:
            return
        try:
            self.shop.add_to_cart(sku, quantity)
            self.refresh_all()
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Could not add item", str(exc), parent=self.root)

    def remove_cart_quantity(self):
        sku = self._selected_sku(self.cart_tree)
        if sku is None:
            return
        quantity = simpledialog.askinteger("Remove from cart", "Quantity to remove:", minvalue=1, parent=self.root)
        if quantity is None:
            return
        try:
            self.shop.remove_from_cart(sku, quantity)
            self.refresh_cart()
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Could not remove item", str(exc), parent=self.root)

    def clear_cart(self):
        if self.shop.cart.is_empty():
            return
        if messagebox.askyesno("Clear cart", "Remove all items from the cart?", parent=self.root):
            self.shop.cancel_cart()
            self.refresh_cart()

    def add_product_dialog(self):
        self._product_dialog("Add product")

    def edit_product_dialog(self):
        sku = self._selected_sku(self.inventory_tree)
        if sku is not None:
            self._product_dialog("Edit product", self.shop.get_product(sku))

    def _product_dialog(self, title, product=None):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.configure(bg=self.BG)

        fields = [
            ("SKU", "SKU"), ("Name", "Name"), ("Category", "Category"),
            ("Unit cost", "Unit_Cost"), ("Selling price", "Selling_Price"),
            ("Stock", "Stock"), ("Reorder level", "Reorder_Level"),
        ]
        entries = {}
        for row, (label, key) in enumerate(fields):
            ttk.Label(dialog, text=label).grid(row=row, column=0, sticky="w", padx=16, pady=7)
            entry = ttk.Entry(dialog, width=30)
            entry.grid(row=row, column=1, padx=16, pady=7)
            if product is not None:
                entry.insert(0, str(getattr(product, key)))
            if product is not None and key == "SKU":
                entry.configure(state="readonly")
            entries[key] = entry

        photo_choice = {"source": None, "remove": False}
        current_photo = product.Image if product else ""
        photo_label = ttk.Label(dialog, text=current_photo or "No image selected", width=30)
        photo_label.grid(row=len(fields), column=1, sticky="w", padx=16, pady=5)
        ttk.Label(dialog, text="Product photo").grid(row=len(fields), column=0, sticky="w", padx=16, pady=5)

        def choose_photo():
            selected_path = filedialog.askopenfilename(
                parent=dialog,
                title="Choose product photo",
                filetypes=[("Image files", "*.png *.jpg *.jpeg *.webp *.gif *.bmp"), ("All files", "*.*")],
            )
            if selected_path:
                photo_choice["source"] = selected_path
                photo_choice["remove"] = False
                photo_label.configure(text=Path(selected_path).name)

        def clear_photo():
            photo_choice["source"] = None
            photo_choice["remove"] = True
            photo_label.configure(text="No image selected")

        photo_buttons = ttk.Frame(dialog)
        photo_buttons.grid(row=len(fields) + 1, column=1, sticky="w", padx=16)
        ttk.Button(photo_buttons, text="Choose photo", command=choose_photo).pack(side="left")
        ttk.Button(photo_buttons, text="Remove photo", command=clear_photo).pack(side="left", padx=(6, 0))

        active_var = tk.BooleanVar(value=product.Active if product else True)
        if product:
            ttk.Checkbutton(dialog, text="Active", variable=active_var).grid(
                row=len(fields) + 2, column=1, sticky="w", padx=16, pady=5
            )

        def save():
            try:
                values = {key: entry.get().strip() for key, entry in entries.items()}
                if product is None and values["SKU"] in self.shop.products:
                    raise ValueError(f"A product with SKU {values['SKU']} already exists")
                existing_image = product.Image if product else ""
                candidate = Product(
                    SKU=values["SKU"], Name=values["Name"], Category=values["Category"],
                    Unit_Cost=values["Unit_Cost"], Selling_Price=values["Selling_Price"],
                    Stock=int(values["Stock"]), Reorder_Level=int(values["Reorder_Level"]),
                    Image=existing_image,
                )
                if photo_choice["source"]:
                    candidate.Image = self._copy_product_image(photo_choice["source"], candidate.SKU)
                elif photo_choice["remove"]:
                    candidate.Image = ""

                if product is None:
                    self.shop.add_product(candidate)
                else:
                    self.shop.update_product(
                        product.SKU,
                        Name=values["Name"], Category=values["Category"],
                        Unit_Cost=values["Unit_Cost"], Selling_Price=values["Selling_Price"],
                        Stock=int(values["Stock"]), Reorder_Level=int(values["Reorder_Level"]),
                        Active=active_var.get(),
                    )
                    product.Image = candidate.Image
                self._save_after_change()
                self.refresh_all()
                dialog.destroy()
            except (ValueError, TypeError) as exc:
                messagebox.showerror("Invalid product", str(exc), parent=dialog)

        def row_for_buttons():
            return len(fields) + (3 if product else 2)

        buttons = ttk.Frame(dialog)
        buttons.grid(row=row_for_buttons(), column=0, columnspan=2, sticky="e", padx=16, pady=14)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=save).pack(side="right")

    def _copy_product_image(self, source_path, sku):
        source = Path(source_path).resolve()
        if not source.is_file():
            raise ValueError("Selected photo file does not exist")
        try:
            with PILImage.open(source) as image:
                image.verify()
        except (OSError, ValueError) as exc:
            raise ValueError("Selected file is not a supported image") from exc

        safe_sku = re.sub(r"[^A-Za-z0-9_-]+", "_", str(sku)).strip("_") or "product"
        suffix = source.suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}:
            raise ValueError("Choose a PNG, JPEG, WebP, GIF, or BMP image")
        self.product_image_dir.mkdir(parents=True, exist_ok=True)
        destination = self.product_image_dir / f"{safe_sku}{suffix}"
        if source != destination.resolve():
            shutil.copy2(source, destination)
        return destination.name

    def restock_selected(self):
        sku = self._selected_sku(self.inventory_tree)
        if sku is None:
            return
        quantity = simpledialog.askinteger("Restock", "Quantity to add:", minvalue=1, parent=self.root)
        if quantity is None:
            return
        try:
            self.shop.restock_product(sku, quantity)
            self._save_after_change()
            self.refresh_inventory()
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Could not restock", str(exc), parent=self.root)

    def deactivate_selected(self):
        sku = self._selected_sku(self.inventory_tree)
        if sku is None:
            return
        product = self.shop.get_product(sku)
        if not product.Active:
            messagebox.showinfo("Already inactive", "This product is already inactive.", parent=self.root)
            return
        if messagebox.askyesno("Deactivate product", f"Deactivate {product.Name}?", parent=self.root):
            self.shop.deactivate_product(sku)
            self._save_after_change()
            self.refresh_inventory()

    def checkout(self):
        if self.shop.cart.is_empty():
            messagebox.showinfo("Empty cart", "Add at least one item before checkout.", parent=self.root)
            return
        try:
            discount = float(self.discount_var.get().strip() or "0")
            next_sale_id = self._next_sale_id()
            order = self.shop.checkout(discount_percent=discount)
            order.sale_id = next_sale_id
        except (OSError, ValueError, TypeError) as exc:
            messagebox.showerror("Checkout failed", str(exc), parent=self.root)
            return

        save_errors = []
        try:
            self._append_sale_to_history(order)
        except (OSError, ValueError, TypeError) as exc:
            save_errors.append(f"Sales history: {exc}")

        inventory_error = self._save_after_change(show_error=False)
        if inventory_error:
            save_errors.append(f"Inventory: {inventory_error}")
        self.discount_var.set("0")
        self.refresh_all()
        self._show_receipt(order)
        if save_errors:
            messagebox.showwarning(
                "Sale completed; a data file was not saved",
                "The sale completed, but one or more files could not be updated:\n\n"
                + "\n".join(save_errors),
                parent=self.root,
            )

    def _append_sale_to_history(self, order):
        if self.sales_path.exists():
            with self.sales_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        else:
            data = {"sales": []}

        if not isinstance(data, dict) or not isinstance(data.get("sales"), list):
            raise ValueError("sales.json must contain a sales list")

        sale_time = datetime.fromisoformat(order.timestamp).astimezone()
        sale_date = sale_time.strftime("%Y-%m-%d")
        new_rows = [
            {
                "Sale ID": order.sale_id,
                "Date": sale_date,
                "SKU": item["sku"],
                "Quantity": item["quantity"],
                "Unit selling price at sale": item["unit_selling_price"],
                "Unit cost at sale": item["unit_cost"],
                "Discount %": order.discount_percent,
            }
            for item in order.items
        ]
        data["sales"].extend(new_rows)
        with self.sales_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4, allow_nan=False)

    def _next_sale_id(self):
        if not self.sales_path.exists():
            return "S001"
        with self.sales_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict) or not isinstance(data.get("sales"), list):
            raise ValueError("sales.json must contain a sales list")

        highest_number = 0
        for sale in data["sales"]:
            if not isinstance(sale, dict):
                continue
            match = re.fullmatch(r"S(\d+)", str(sale.get("Sale ID", "")).strip(), re.IGNORECASE)
            if match:
                highest_number = max(highest_number, int(match.group(1)))
        return f"S{highest_number + 1:03d}"

    def open_analysis(self):
        password = simpledialog.askstring(
            "Analysis access", "Enter the analysis password:", show="*", parent=self.root
        )
        if password is None:
            return
        if password != "1234":
            messagebox.showerror("Access denied", "The password is incorrect.", parent=self.root)
            return
        try:
            from ShopPilot_analysis import run_analysis
            results = run_analysis(Path(__file__).resolve().parent)
        except ImportError as exc:
            messagebox.showerror(
                "Analysis dependency missing",
                f"Install the project requirements before opening analysis.\n\n{exc}",
                parent=self.root,
            )
            return
        except Exception as exc:
            messagebox.showerror("Analysis could not be created", str(exc), parent=self.root)
            return
        self._show_analysis_window(results)

    def _show_analysis_window(self, results):
        window = tk.Toplevel(self.root)
        window.title("ShopPilot | Business Analysis")
        window.geometry("1080x720")
        window.minsize(850, 560)
        window.configure(bg=self.BG)

        header = tk.Frame(window, bg=self.NAVY, padx=20, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="Business Analysis", bg=self.NAVY, fg=self.BG,
                 font=("Segoe UI", 19, "bold")).pack(anchor="w")
        metrics = results["metrics"]
        tk.Label(
            header,
            text=f"Reporting period: {metrics['reporting_period']}   ·   Includes {metrics['sales_rows']} rows from sales.json",
            bg=self.NAVY, fg=self.PALE_BLUE, font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 0))

        summary = ttk.Frame(window, padding=14)
        summary.pack(fill="x")
        top_text = f"{metrics['top_sku']} ({metrics['top_quantity']} units)"
        cards = [
            ("Revenue", metrics["revenue"]),
            ("Cost", metrics["cost"]),
            ("Gross profit", metrics["gross_profit"]),
            ("Top-selling SKU", top_text),
        ]
        for index, (label, value) in enumerate(cards):
            card = tk.Frame(summary, bg=self.PALE_BLUE, padx=14, pady=10,
                            highlightthickness=1, highlightbackground=self.STEEL_BLUE)
            card.grid(row=0, column=index, sticky="nsew", padx=5)
            summary.columnconfigure(index, weight=1)
            tk.Label(card, text=label, bg=self.PALE_BLUE, fg=self.MID_BLUE,
                     font=("Segoe UI", 9)).pack(anchor="w")
            shown = f"EGP {value:,.2f}" if isinstance(value, (int, float)) else value
            tk.Label(card, text=shown, bg=self.PALE_BLUE, fg=self.NAVY,
                     font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(4, 0))

        tabs = ttk.Notebook(window)
        tabs.pack(fill="both", expand=True, padx=18, pady=(0, 8))
        table_specs = [
            ("Sales", results["sales"]),
            ("Products", results["products"]),
            ("By category", results["category_summary"]),
            ("Low stock", results["low_stock"]),
            ("Supplier recommendations", results["recommendations"]),
        ]
        for title, frame in table_specs:
            tab = ttk.Frame(tabs, padding=8)
            tabs.add(tab, text=title)
            self._populate_analysis_table(tab, frame)

        details_tab = ttk.Frame(tabs, padding=10)
        tabs.add(details_tab, text="Data checks")
        details_tab.rowconfigure(0, weight=1)
        details_tab.columnconfigure(0, weight=1)
        details = tk.Text(details_tab, wrap="word", bg=self.BG, fg=self.NAVY,
                          font=("Consolas", 9), padx=12, pady=10)
        details.grid(row=0, column=0, sticky="nsew")
        details_scroll = ttk.Scrollbar(details_tab, orient="vertical", command=details.yview)
        details_scroll.grid(row=0, column=1, sticky="ns")
        details.configure(yscrollcommand=details_scroll.set)
        exploration = results["exploration"]
        details.insert(
            "1.0",
            "DATAFRAME OVERVIEW\n"
            f"Shape: {exploration['shape']}\n"
            f"Columns: {', '.join(exploration['columns'])}\n\n"
            f"Data types:\n{exploration['dtypes']}\n\n"
            f"DataFrame info:\n{exploration['info']}\n"
            f"Statistical summary:\n{exploration['describe'].to_string()}\n\n"
            f"head():\n{exploration['head'].to_string(index=False)}\n\n"
            f"Column selection:\n{exploration['selected_columns'].to_string(index=False)}\n\n"
            f"loc example:\n{exploration['loc_example'].to_string(index=False)}\n\n"
            f"iloc example:\n{exploration['iloc_example'].to_string(index=False)}\n\n"
            f"Conditional filter (gross profit > 0):\n{exploration['conditional_filter'].to_string(index=False)}\n\n"
            f"query('Quantity > 0') example:\n{exploration['query_example'].to_string(index=False)}\n\n"
            f"Sorted by revenue:\n{exploration['sorted_by_revenue'].to_string(index=False)}\n\n"
            f"Product name Series:\n{exploration['product_name_series'].to_string(index=False)}\n\n"
            f"Cleaning choices:\n{results['cleaning_explanation']}\n\n"
            f"Empty-sales result:\n{results['empty_sales_result']}\n\n"
            f"Excel round trip:\n{results['excel_status']}\n\n"
            f"Reports saved to:\n{results['report_dir']}"
        )
        details.configure(state="disabled")

        ttk.Button(window, text="Close", command=window.destroy).pack(pady=(0, 12))

    def _populate_analysis_table(self, parent, frame):
        if frame.empty:
            ttk.Label(parent, text="No records to display.").pack(anchor="w", padx=12, pady=12)
            return

        columns = [str(column) for column in frame.columns]
        table = ttk.Treeview(parent, columns=columns, show="headings")
        for column in columns:
            table.heading(column, text=column)
            width = 150 if len(column) > 12 else 105
            table.column(column, width=width, minwidth=70, stretch=True, anchor="w")
        vertical = ttk.Scrollbar(parent, orient="vertical", command=table.yview)
        horizontal = ttk.Scrollbar(parent, orient="horizontal", command=table.xview)
        table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)

        import pandas as pd
        for _, record in frame.iterrows():
            values = []
            for column, value in record.items():
                if pd.isna(value):
                    values.append("")
                elif hasattr(value, "strftime"):
                    values.append(value.strftime("%Y-%m-%d"))
                elif isinstance(value, float):
                    values.append(f"{value:,.2f}")
                else:
                    values.append(str(value))
            table.insert("", "end", values=values)

    def _show_receipt(self, order):
        window = tk.Toplevel(self.root)
        window.title("Sale receipt")
        window.transient(self.root)
        window.geometry("520x500")
        window.configure(bg="white")
        text = tk.Text(window, wrap="word", font=("Consolas", 10), padx=18, pady=18,
                       bg="white", fg=self.TEXT, relief="flat")
        text.pack(fill="both", expand=True)
        text.insert("1.0", self.shop.format_receipt(order))
        text.configure(state="disabled")
        actions = ttk.Frame(window, padding=(12, 0, 12, 12))
        actions.pack(fill="x")
        ttk.Button(actions, text="Close", command=window.destroy).pack(side="right")
        ttk.Button(actions, text="Print receipt", command=self._print_receipt_placeholder).pack(side="right", padx=(0, 8))

    def _print_receipt_placeholder(self):
        messagebox.showinfo(
            "Printer setup",
            "Receipt printing will be connected to a printer in a future update.",
            parent=self.root,
        )

    def _save_after_change(self, show_error=True):
        try:
            self.shop.save_inventory(self.inventory_path)
            return None
        except OSError as exc:
            if show_error:
                messagebox.showerror("Could not save inventory", str(exc), parent=self.root)
            return str(exc)

    def save_inventory(self):
        error = self._save_after_change()
        if error is None:
            messagebox.showinfo("Saved", "Inventory saved successfully.", parent=self.root)


def main():
    root = tk.Tk()
    ShopPilotApp(root)
    root.mainloop()
