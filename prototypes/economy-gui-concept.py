import tkinter as tk
from tkinter import scrolledtext, ttk
import logging
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# If your simulation is in simulation.py:
from simulation import Simulation


class LogCaptureHandler(logging.Handler):
    def __init__(self, level=logging.INFO):
        super().__init__(level)
        self.records = []

    def emit(self, record):
        msg = self.format(record)
        self.records.append(msg)


class SimGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Economy Simulation")

        self.log_capture_handler = LogCaptureHandler()
        formatter = logging.Formatter("[%(levelname)s] %(message)s")
        self.log_capture_handler.setFormatter(formatter)
        logging.getLogger().addHandler(self.log_capture_handler)

        self.sim = Simulation()
        self.sim.initialize_sim()

        top_frame = tk.Frame(root)
        top_frame.pack(side=tk.TOP, fill=tk.X)

        self.day_label_var = tk.StringVar(value=f"Current Day: {self.sim.current_day}")
        tk.Label(top_frame, textvariable=self.day_label_var).pack(side=tk.LEFT, padx=5)

        tk.Button(top_frame, text="Step 1 Day", command=self.step_one_day).pack(side=tk.LEFT, padx=5)
        self.days_entry = tk.Entry(top_frame, width=5)
        self.days_entry.insert(0, "10")
        self.days_entry.pack(side=tk.LEFT, padx=2)
        tk.Button(top_frame, text="Run X Days", command=self.run_multiple_days).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="Summary", command=self.show_summary).pack(side=tk.LEFT, padx=5)

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Logs tab
        self.logs_frame = tk.Frame(self.notebook)
        self.logs_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.logs_frame, text="Logs")

        self.log_area = scrolledtext.ScrolledText(self.logs_frame, wrap=tk.WORD, width=80, height=15)
        self.log_area.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Resources tab
        self.resources_frame = tk.Frame(self.notebook)
        self.resources_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.resources_frame, text="Resources")

        self.resource_tree = ttk.Treeview(
            self.resources_frame,
            columns=("resource", "supply", "demand", "price"),
            show="headings"
        )
        self.resource_tree.heading("resource", text="Resource")
        self.resource_tree.heading("supply", text="Supply")
        self.resource_tree.heading("demand", text="Demand")
        self.resource_tree.heading("price", text="Price")
        self.resource_tree.column("resource", width=100)
        self.resource_tree.column("supply", width=80)
        self.resource_tree.column("demand", width=80)
        self.resource_tree.column("price", width=80)
        self.resource_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll_y = ttk.Scrollbar(self.resources_frame, orient="vertical", command=self.resource_tree.yview)
        self.resource_tree.configure(yscroll=scroll_y.set)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)

        # Forest chart tab
        self.forest_frame = tk.Frame(self.notebook)
        self.forest_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.forest_frame, text="Forest Chart")

        self.forest_fig = Figure(figsize=(5, 4), dpi=100)
        self.ax_forest = self.forest_fig.add_subplot(111)
        self.forest_canvas = FigureCanvasTkAgg(self.forest_fig, master=self.forest_frame)
        self.forest_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Hungry chart tab
        self.hungry_frame = tk.Frame(self.notebook)
        self.hungry_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.hungry_frame, text="Hungry Chart")

        self.hungry_fig = Figure(figsize=(5, 4), dpi=100)
        self.ax_hungry = self.hungry_fig.add_subplot(111)
        self.hungry_canvas = FigureCanvasTkAgg(self.hungry_fig, master=self.hungry_frame)
        self.hungry_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Gold supply tab
        self.gold_frame = tk.Frame(self.notebook)
        self.gold_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.gold_frame, text="Gold Supply")

        self.gold_fig = Figure(figsize=(10, 6), dpi=100)
        self.ax_gold_line = self.gold_fig.add_subplot(221)
        self.ax_gold_job = self.gold_fig.add_subplot(222)
        self.ax_gold_top = self.gold_fig.add_subplot(223)
        self.gold_canvas = FigureCanvasTkAgg(self.gold_fig, master=self.gold_frame)
        self.gold_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Guilds tab
        self.guilds_frame = tk.Frame(self.notebook)
        self.guilds_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.guilds_frame, text="Guilds")

        self.guilds_tree = ttk.Treeview(
            self.guilds_frame,
            columns=("guild_id", "name", "profession", "employees", "silver", "gold", "loan_balance"),
            show="headings"
        )
        self.guilds_tree.heading("guild_id", text="ID")
        self.guilds_tree.heading("name", text="Name")
        self.guilds_tree.heading("profession", text="Profession")
        self.guilds_tree.heading("employees", text="# Employees")
        self.guilds_tree.heading("silver", text="Silver")
        self.guilds_tree.heading("gold", text="Gold")
        self.guilds_tree.heading("loan_balance", text="Loan")

        self.guilds_tree.column("guild_id", width=50)
        self.guilds_tree.column("name", width=120)
        self.guilds_tree.column("profession", width=100)
        self.guilds_tree.column("employees", width=80)
        self.guilds_tree.column("silver", width=80)
        self.guilds_tree.column("gold", width=80)
        self.guilds_tree.column("loan_balance", width=80)

        self.guilds_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll_guilds = ttk.Scrollbar(self.guilds_frame, orient="vertical", command=self.guilds_tree.yview)
        self.guilds_tree.configure(yscroll=scroll_guilds.set)
        scroll_guilds.pack(side=tk.RIGHT, fill=tk.Y)

        # Treasury tab
        self.treasury_frame = tk.Frame(self.notebook)
        self.treasury_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.treasury_frame, text="Treasury")

        self.treasury_tree = ttk.Treeview(
            self.treasury_frame,
            columns=("silver", "gold"),
            show="headings"
        )
        self.treasury_tree.heading("silver", text="Silver")
        self.treasury_tree.heading("gold", text="Gold")
        self.treasury_tree.column("silver", width=120)
        self.treasury_tree.column("gold", width=120)
        self.treasury_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll_treasury = ttk.Scrollbar(
            self.treasury_frame,
            orient="vertical",
            command=self.treasury_tree.yview
        )
        self.treasury_tree.configure(yscroll=scroll_treasury.set)
        scroll_treasury.pack(side=tk.RIGHT, fill=tk.Y)

        # >>> NEW: Order Book tab <<<
        self.order_book_frame = tk.Frame(self.notebook)
        self.order_book_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.order_book_frame, text="Order Book")

        self.order_tree = ttk.Treeview(
            self.order_book_frame,
            columns=("item","type","price","quantity","owner"),
            show="headings"
        )
        self.order_tree.heading("item", text="Item")
        self.order_tree.heading("type", text="Type")
        self.order_tree.heading("price", text="Price")
        self.order_tree.heading("quantity", text="Quantity")
        self.order_tree.heading("owner", text="Owner")

        self.order_tree.column("item", width=100)
        self.order_tree.column("type", width=60)
        self.order_tree.column("price", width=80)
        self.order_tree.column("quantity", width=80)
        self.order_tree.column("owner", width=120)

        self.order_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scroll_order = ttk.Scrollbar(
            self.order_book_frame,
            orient="vertical",
            command=self.order_tree.yview
        )
        self.order_tree.configure(yscroll=scroll_order.set)
        scroll_order.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 1) Population tab
        self.population_frame = tk.Frame(self.notebook)
        self.population_frame.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.population_frame, text="Population")

        # 2) Define columns for the table
        self.population_tree = ttk.Treeview(
            self.population_frame,
            columns=("id", "name", "profession", "silver", "gold", "inventory"),
            show="headings"
        )
        self.population_tree.heading("id", text="ID")
        self.population_tree.heading("name", text="Name")
        self.population_tree.heading("profession", text="Profession")
        self.population_tree.heading("silver", text="Silver")
        self.population_tree.heading("gold", text="Gold")
        self.population_tree.heading("inventory", text="Inventory")

        # Optional: set column widths
        self.population_tree.column("id", width=40, anchor=tk.CENTER)
        self.population_tree.column("name", width=120)
        self.population_tree.column("profession", width=100)
        self.population_tree.column("silver", width=70, anchor=tk.E)
        self.population_tree.column("gold", width=70, anchor=tk.E)
        self.population_tree.column("inventory", width=600)  # or something wide to display items

        self.population_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Add a vertical scrollbar
        scroll_pop = ttk.Scrollbar(self.population_frame, orient="vertical", command=self.population_tree.yview)
        self.population_tree.configure(yscroll=scroll_pop.set)
        scroll_pop.pack(side=tk.RIGHT, fill=tk.Y)

        # finally, refresh once
        self.refresh_logs()
        self.refresh_resource_table()
        self.refresh_treasury_table()
        self.refresh_guilds_table()
        self.plot_all_charts()
        self.refresh_order_book_table()  # new

    def step_one_day(self):
        try:
            self.sim.run_days(1)
        except Exception as e:
            logging.exception("Crash on day %s. Reason:", self.sim.current_day)
            raise
        self.day_label_var.set(f"Current Day: {self.sim.current_day}")
        self.refresh_logs()
        self.refresh_resource_table()
        self.refresh_treasury_table()
        self.refresh_guilds_table()
        self.refresh_order_book_table()  # new
        self.refresh_population_table()
        self.plot_all_charts()

    def run_multiple_days(self):
        try:
            d = int(self.days_entry.get())
        except:
            d = 10
        self.sim.run_days(d)
        self.day_label_var.set(f"Current Day: {self.sim.current_day}")
        self.refresh_logs()
        self.refresh_resource_table()
        self.refresh_treasury_table()
        self.refresh_guilds_table()
        self.refresh_order_book_table()  # new
        self.refresh_population_table()
        self.plot_all_charts()

    def refresh_logs(self):
        self.log_area.delete("1.0", tk.END)
        for msg in self.log_capture_handler.records:
            self.log_area.insert(tk.END, msg + "\n")
        self.log_area.see(tk.END)

    def refresh_resource_table(self):
        for row in self.resource_tree.get_children():
            self.resource_tree.delete(row)
        # pull from self.sim.marketWarehouse.goods
        for resource, data in sorted(self.sim.marketWarehouse.goods.items()):
            sup_int = int(round(data["supply"]))
            dem_int = int(round(data["demand"]))
            prc_float = f"{data['price']:.2f}"
            self.resource_tree.insert("", tk.END, values=(resource, sup_int, dem_int, prc_float))

    def refresh_treasury_table(self):
        for row in self.treasury_tree.get_children():
            self.treasury_tree.delete(row)

        treasury = self.sim.treasury
        silver_str = f"{treasury.silver:.2f}"
        gold_str = f"{treasury.gold:.2f}"
        self.treasury_tree.insert("", tk.END, values=(silver_str, gold_str))

    def refresh_guilds_table(self):
        for row in self.guilds_tree.get_children():
            self.guilds_tree.delete(row)
        for g in self.sim.guilds:
            guild_id = g.guild_id
            guild_name = g.guild_name
            profession = g.profession.value
            num_employees = len(g.employees)
            silver_str = f"{g.silver:.2f}"
            gold_str = f"{g.gold:.2f}"
            lb = f"{g.loan_balance:.2f}"
            self.guilds_tree.insert(
                "",
                tk.END,
                values=(guild_id, guild_name, profession, num_employees, silver_str, gold_str, lb)
            )

    def refresh_order_book_table(self):
        """ Show all open BIDs and ASKs in our order book """
        # clear existing
        for row in self.order_tree.get_children():
            self.order_tree.delete(row)

        # BIDs
        for item, bid_list in self.sim.marketWarehouse.bids.items():
            for b in bid_list:
                order_type = "BID"
                owner_name = getattr(b.owner, "guild_name", getattr(b.owner, "name", "???"))
                prc = f"{b.price:.2f}"
                qty = f"{b.quantity:.2f}"
                self.order_tree.insert("", tk.END, values=(item, order_type, prc, qty, owner_name))

        # ASKs
        for item, ask_list in self.sim.marketWarehouse.asks.items():
            for a in ask_list:
                order_type = "ASK"
                owner_name = getattr(a.owner, "guild_name", getattr(a.owner, "name", "???"))
                prc = f"{a.price:.2f}"
                qty = f"{a.quantity:.2f}"
                self.order_tree.insert("", tk.END, values=(item, order_type, prc, qty, owner_name))


    def refresh_population_table(self):
        """
        Clears and repopulates the 'Population' tab with
        each Person's ID, Name, Profession, Silver, Gold, and summarized inventory.
        """
        # Clear existing rows
        for row in self.population_tree.get_children():
            self.population_tree.delete(row)

        # Insert each person
        for p in self.sim.people:
            person_id = p.person_id
            name = p.name
            prof = p.profession.value
            silver_str = f"{p.silver:.2f}"
            gold_str = f"{p.gold:.2f}"

            # Summarize inventory in one string, e.g. "wood=10, grain=5"
            # Only show items with a positive amount
            inv_items = []
            for item_name, qty in sorted(p.inventory.items()):
                if qty > 0:
                    inv_items.append(f"{item_name}={int(qty)}")
            inventory_str = ", ".join(inv_items)

            self.population_tree.insert(
                "",
                tk.END,
                values=(person_id, name, prof, silver_str, gold_str, inventory_str)
            )
        
    def plot_all_charts(self):
        # Rebuild forest chart
        self.ax_forest.clear()
        days = self.sim.day_list
        forest_vals = self.sim.forest_capacity_list
        self.ax_forest.plot(days, forest_vals, color="green", label="Forest")
        self.ax_forest.set_title("Forest Capacity Over Time")
        self.ax_forest.set_xlabel("Day")
        self.ax_forest.set_ylabel("Forest Cap")
        self.ax_forest.legend()
        self.forest_canvas.draw()

        # Rebuild hungry chart
        self.ax_hungry.clear()
        hungry_vals = self.sim.hungry_list
        self.ax_hungry.plot(days, hungry_vals, color="red", label="Hungry")
        self.ax_hungry.set_title("Hungry Count Over Time")
        self.ax_hungry.set_xlabel("Day")
        self.ax_hungry.set_ylabel("People Hungry")
        self.ax_hungry.legend()
        self.hungry_canvas.draw()

        # Rebuild gold supply charts
        self.ax_gold_line.clear()
        self.ax_gold_job.clear()
        self.ax_gold_top.clear()

        gold_vals = self.sim.total_gold_list
        self.ax_gold_line.plot(days, gold_vals, color="gold", label="Total Gold")
        self.ax_gold_line.set_title("Total Gold vs Day")
        self.ax_gold_line.set_xlabel("Day")
        self.ax_gold_line.set_ylabel("Gold Coins")
        self.ax_gold_line.legend()

        # gold by job
        job_gold_map = {}
        for p in self.sim.people:
            j = p.profession.value
            job_gold_map[j] = job_gold_map.get(j, 0) + p.gold
        jobs = list(job_gold_map.keys())
        amounts = [job_gold_map[j] for j in jobs]
        self.ax_gold_job.bar(jobs, amounts, color="orange")
        self.ax_gold_job.set_title("Current Gold by Profession")
        self.ax_gold_job.set_yscale("log")
        self.ax_gold_job.set_xticklabels(jobs, rotation=45, ha="right")


    def show_summary(self):
        summary = self.sim.summarize()
        self.log_area.insert(tk.END, f"\n[SUMMARY] {summary}\n")
        self.log_area.see(tk.END)
